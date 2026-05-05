import logging
import re
from typing import Optional

log = logging.getLogger(__name__)

# SanMar filename pattern example: "PC61_Black_Front.jpg"
# Pattern: {Style}_{Color}_{Type}.{Ext}
SANMAR_FILENAME_REGEX = re.compile(r"^(?P<style>[^_]+)_(?P<color>[^_]+)_(?P<type>[^_.]+)\.(?P<ext>.+)$", re.IGNORECASE)

class SanMarFTPClient:
    """
    Mocked SanMar FTP client to list and retrieve bulk images.
    """
    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password

    async def list_images(self, directory: str = "/") -> list[dict]:
        """
        Lists images and maps them to product/color/type metadata.
        """
        log.info(f"MOCK: Connecting to SanMar FTP at {self.host}...")
        
        # In a real implementation, we would use aioftp or similar
        # For now, return a sample list
        mock_files = [
            "PC61_Black_Front.jpg",
            "PC61_Black_Back.jpg",
            "PC61_White_Front.jpg",
            "LPC61_Navy_Front.jpg"
        ]
        
        results = []
        for filename in mock_files:
            match = SANMAR_FILENAME_REGEX.match(filename)
            if match:
                results.append({
                    "filename": filename,
                    "style": match.group("style"),
                    "color": match.group("color"),
                    "type": match.group("type"),
                    "url": f"ftp://{self.host}/{filename}" # Internal FTP URL
                })
        
        return results

def map_sanmar_type(raw_type: str) -> str:
    """
    Maps SanMar image types to internal enum: front | back | side | detail | lifestyle
    """
    t = raw_type.lower()
    if t in ("front", "primary"):
        return "front"
    if t in ("back", "rear"):
        return "back"
    if t == "side":
        return "side"
    if t == "swatch":
        return "detail"
    return "lifestyle"
