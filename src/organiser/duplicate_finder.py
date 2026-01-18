import hashlib
from typing import Dict, List, Tuple, Optional


class DuplicateFinder:
    def __init__(self):
        self.hash_map: Dict[str, List[str]] = {}
        self.duplicates: List[Tuple[str, str]] = []  # (original, duplicate)

    @staticmethod
    def compute_hash(path: str, chunk_size: int = 65536) -> Optional[str]:
        try:
            hasher = hashlib.sha256()
            with open(path, "rb") as f:
                while chunk := f.read(chunk_size):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None

    def check_and_record(self, path: str) -> bool:
        """Returns True if duplicate, False otherwise. Records hash."""
        file_hash = self.compute_hash(path)
        if not file_hash:
            return False
        if file_hash in self.hash_map:
            self.duplicates.append((self.hash_map[file_hash][0], path))
            self.hash_map[file_hash].append(path)
            return True
        else:
            self.hash_map[file_hash] = [path]
            return False

    def get_duplicates(self) -> List[Tuple[str, str]]:
        return self.duplicates
