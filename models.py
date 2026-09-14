from dataclasses import dataclass
from typing import Optional

@dataclass(slots=True)
class Deal:
    store: str
    title: str
    current_price: float
    old_price: Optional[float]
    url: str
    image_url: Optional[str] = None
    external_id: Optional[str] = None
    category: Optional[str] = None

    @property
    def saving(self) -> float:
        if not self.old_price:
            return 0.0
        return max(0.0, self.old_price - self.current_price)

    @property
    def discount_percent(self) -> float:
        if not self.old_price or self.old_price <= 0:
            return 0.0
        return round((self.saving / self.old_price) * 100, 1)
