# -*- coding: utf-8 -*-
"""Trilium integration service."""

import os
import time
import html
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Any, Optional
import trilium_py.client
from trilium_py.client import ETAPI
from app.core.config import Config

# Monkey patch trilium_py to use a shared session with retry logic
# This prevents WinError 10048 (socket exhaustion) by reusing TCP connections
def get_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=1,  # 1s, 2s, 4s, 8s, 16s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=20,  # Increase pool size
        pool_maxsize=20
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# Apply monkey patch
shared_session = get_session()
trilium_py.client.requests = shared_session

class TriliumService:
    """Service for interacting with Trilium Notes."""

    def __init__(self, config: Config):
        """Initialize the service.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.client = None
        self.note_ids = config.note_ids
        self.depth = config.depth
        self.limit = config.limit
        self._connect()

    def _connect(self):
        """Establish connection to Trilium ETAPI."""
        try:
            print(f"Connecting to Trilium at {self.config.trilium_base_url}...")
            self.client = ETAPI(self.config.trilium_base_url, self.config.trilium_token)
            # Verify connection by getting app info or root note
            try:
                self.client.get_app_info()
                print("Successfully connected to Trilium.")
            except Exception:
                print("Warning: Could not verify Trilium connection (get_app_info failed).")
        except Exception as e:
            print(f"Failed to connect to Trilium: {e}")
            self.client = None

    def load_documents(self) -> List[Dict[str, Any]]:
        """Load documents from Trilium.
        
        Returns:
            List of documents (dictionaries)
        """
        documents = []
        if self.client:
            self._try_load_real_documents(documents)
        else:
            print("No Trilium connection, returning empty list.")
        return documents

    def _try_load_real_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Try to load real documents from Trilium using BFS with filtering.
        
        Args:
            documents: List to append loaded documents to
        """
        if not self.client:
            return
            
        try:
            note_ids_to_process = self.note_ids
            print(f"Preparing to load documents from note IDs: {note_ids_to_process}")
            
            total_processed = 0
            total_skipped = 0
            total_errors = 0
            
            # Binary/Non-text MIME types to skip
            binary_types = [
                'image', 'application/pdf', 'application/zip', 
                'application/octet-stream', 'application/x-zip-compressed',
                'application/x-compressed', 'application/x-tar',
                'application/gzip', 'application/x-gzip',
                'application/x-7z-compressed', 'application/x-rar-compressed'
            ]
            
            for root_note_id in note_ids_to_process:
                print(f"\n=== Processing Root Note ID: {root_note_id} ===")
                
                # Custom BFS traversal
                from collections import deque
                queue = deque([(root_note_id, 1)])  # (note_id, depth)
                visited = {root_note_id}
                
                processed_count = 0
                skipped_count = 0
                error_count = 0
                
                while queue:
                    # Check for global limit
                    if len(documents) >= self.limit:
                        print(f"Reached maximum document limit: {self.limit}")
                        break
                        
                    current_note_id, current_depth = queue.popleft()
                    
                    # Progress log every 50 scanned items
                    total_scanned = processed_count + skipped_count + error_count
                    if total_scanned > 0 and total_scanned % 50 == 0:
                        print(f"Progress: Scanned {total_scanned} notes (Collected: {len(documents)}, Skipped: {skipped_count}, Queue: {len(queue)})...")
                    
                    # Add small delay to regulate request rate
                    time.sleep(0.01)  # 10ms delay
                    
                    # Retry logic for network operations
                    max_retries = 5  # Increased retries
                    retry_delay = 2
                    
                    try:
                        # Get note details with manual retry wrapper (in addition to session retry)
                        note = None
                        for attempt in range(max_retries):
                            try:
                                note = self.client.get_note(current_note_id)
                                break
                            except Exception as e:
                                error_str = str(e)
                                if "WinError 10048" in error_str or "Connection refused" in error_str:
                                    # Serious socket error, wait longer
                                    print(f"Socket exhaustion detected, waiting 5s... (Attempt {attempt+1}/{max_retries})")
                                    time.sleep(5)
                                elif attempt < max_retries - 1:
                                    time.sleep(retry_delay * (attempt + 1))
                                else:
                                    print(f"Failed to get note {current_note_id} after {max_retries} attempts: {e}")
                                    # Don't raise here, just continue to next note to avoid breaking the whole process
                                    note = None
                                    
                        if not note:
                            error_count += 1
                            continue
                            
                        # Handle legacy format if needed
                        if 'note' in note and 'noteId' not in note:
                            note = note['note']
                            
                        title = note.get('title', 'Untitled')
                        note_type = note.get('type', 'text')
                        mime = note.get('mime', '')
                        
                        # 1. Pre-fetch filtering
                        should_process_content = True
                        if note_type not in ['text', 'code', 'doc', 'book']:
                            # print(f"Skipping non-text type: {title} ({note_type})")
                            should_process_content = False
                            skipped_count += 1
                        elif mime in binary_types or mime.startswith('image/') or mime.startswith('audio/') or mime.startswith('video/'):
                            # print(f"Skipping binary MIME: {title} ({mime})")
                            should_process_content = False
                            skipped_count += 1
                            
                        # 2. Fetch content if valid text type
                        if should_process_content:
                            content = ""
                            try:
                                content_response = None
                                for attempt in range(max_retries):
                                    try:
                                        content_response = self.client.get_note_content(current_note_id)
                                        break
                                    except Exception as e:
                                        error_str = str(e)
                                        if "WinError 10048" in error_str:
                                            print(f"Socket exhaustion detected fetching content, waiting 5s... (Attempt {attempt+1}/{max_retries})")
                                            time.sleep(3)
                                        elif attempt < max_retries - 1:
                                            time.sleep(retry_delay * (attempt + 1))
                                        else:
                                            print(f"Failed to fetch content for {title} after {max_retries} attempts: {e}")
                                            
                                if content_response:
                                    if isinstance(content_response, str):
                                        content = content_response
                                    elif isinstance(content_response, bytes):
                                        # Multi-encoding fallback
                                        try:
                                            content = content_response.decode('utf-8')
                                        except UnicodeDecodeError:
                                            try:
                                                content = content_response.decode('gbk')
                                            except UnicodeDecodeError:
                                                try:
                                                    content = content_response.decode('latin1')
                                                except UnicodeDecodeError:
                                                    print(f"Skipping undecodable content: {title}")
                                    else:
                                        content = str(content_response)
                            except Exception as e:
                                print(f"Error fetching content for {current_note_id}: {e}")
                                
                            # 3. Add to documents if content is valid
                            if content:
                                # Clean HTML content
                                try:
                                    # First unescape HTML entities
                                    content = html.unescape(content)
                                    # Then strip HTML tags using BeautifulSoup
                                    # We use a newline separator to preserve paragraph structure for better chunking
                                    soup = BeautifulSoup(content, "html.parser")
                                    content = soup.get_text(separator="\n", strip=True)
                                except Exception as e:
                                    print(f"Warning: Failed to clean HTML for note {current_note_id}: {e}")
                                    # Fallback to original content if cleaning fails

                            if content and len(content.strip()) > 10:
                                documents.append({
                                    'content': content.strip(),
                                    'title': title,
                                    'note_id': current_note_id,
                                    'attributes': [],
                                    'type': note_type,
                                    'mime': mime
                                })
                                # print(f"✅ [{processed_count+1}] Added: {title}")
                                processed_count += 1
                            else:
                                skipped_count += 1
                                
                        # 4. Enqueue children
                        if current_depth < self.depth:
                            child_ids = note.get('childNoteIds', [])
                            for child_id in child_ids:
                                if child_id not in visited:
                                    visited.add(child_id)
                                    queue.append((child_id, current_depth + 1))
                                    
                    except KeyboardInterrupt:
                        raise  # Re-raise to be handled by caller
                    except Exception as e:
                        print(f"Error processing note {current_note_id}: {e}")
                        error_count += 1
                        
                total_processed += processed_count
                total_skipped += skipped_count
                total_errors += error_count
                
                print(f"\n=== Root Note {root_note_id} Finished ===")
                print(f"Processed: {processed_count}, Skipped: {skipped_count}, Errors: {error_count}")

            print(f"\n🎯 Total Results:")
            print(f"Total Processed: {total_processed}")
            print(f"Total Skipped: {total_skipped}")
            print(f"Total Errors: {total_errors}")
            print(f"Final Document Count: {len(documents)}")
            
        except KeyboardInterrupt:
            print("\nOperation interrupted by user.")
        except Exception as e:
            print(f"Error loading documents: {e}")
            import traceback
            traceback.print_exc()
            raise
