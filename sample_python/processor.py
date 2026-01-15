"""Sample Python module for LegacyLens demo."""

import json
from typing import List, Optional


class DataProcessor:
    """Process and transform data records."""
    
    def __init__(self, config: dict):
        self.config = config
        self.cache = {}
    
    def validate_record(self, record: dict) -> bool:
        """
        Validate a data record against schema.
        
        Returns True if valid, False otherwise.
        """
        required_fields = self.config.get("required_fields", [])
        
        for field in required_fields:
            if field not in record:
                return False
            if record[field] is None or record[field] == "":
                return False
        
        return True
    
    def transform_records(self, records: List[dict]) -> List[dict]:
        """
        Transform a batch of records.
        
        Applies validation and caching for efficiency.
        """
        results = []
        
        for record in records:
            record_id = record.get("id")
            
            # Check cache first
            if record_id and record_id in self.cache:
                results.append(self.cache[record_id])
                continue
            
            # Validate
            if not self.validate_record(record):
                continue
            
            # Transform
            transformed = {
                "id": record_id,
                "data": json.dumps(record),
                "processed": True,
            }
            
            # Cache result
            if record_id:
                self.cache[record_id] = transformed
            
            results.append(transformed)
        
        return results
    
    def clear_cache(self) -> int:
        """Clear the cache and return count of cleared items."""
        count = len(self.cache)
        self.cache = {}
        return count


def calculate_statistics(data: List[float]) -> Optional[dict]:
    """
    Calculate basic statistics for a list of numbers.
    
    Returns None if data is empty.
    """
    if not data:
        return None
    
    n = len(data)
    total = sum(data)
    mean = total / n
    
    # Calculate variance
    variance = sum((x - mean) ** 2 for x in data) / n
    std_dev = variance ** 0.5
    
    return {
        "count": n,
        "sum": total,
        "mean": mean,
        "min": min(data),
        "max": max(data),
        "std_dev": std_dev,
    }
