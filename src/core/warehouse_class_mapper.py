"""
src/core/warehouse_class_mapper.py
----------------------------------
Strict warehouse object classification, confidence policy, and label mapping engine.
Ensures trustworthy identification of warehouse entities (Person, Product/Carton, Pallet, MHE)
and prevents broad aliasing or false classification of unrelated COCO objects.
"""

from typing import Optional, Dict, Set, Tuple
from src.core.warehouse_models import WarehouseObjectCategory


# Canonical label taxonomies
PRODUCT_LABELS: Set[str] = {
    "carton",
    "box",
    "package",
    "parcel",
    "product",
    "cargo",
    "crate",
    "cardboard_box",
    "mattress",
}

PERSON_LABELS: Set[str] = {
    "person",
    "human",
    "worker",
    "operator",
    "handler",
    "employee",
}

PALLET_LABELS: Set[str] = {
    "pallet",
    "wooden_pallet",
    "plastic_pallet",
}

MHE_LABELS: Set[str] = {
    "mhe",
    "forklift",
    "trolley",
    "pallet_jack",
    "hand_truck",
    "reach_truck",
    "stacker",
    "cart",
    "bopt",
    "tow_tractor",
    "truck",
}

# Explicitly excluded from PRODUCT/PACKAGE (personal, office, or unrelated COCO items)
EXCLUDED_NON_WAREHOUSE_LABELS: Set[str] = {
    "cell phone",
    "cell_phone",
    "phone",
    "handbag",
    "backpack",
    "suitcase",
    "bottle",
    "book",
    "laptop",
    "mouse",
    "keyboard",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "remote",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "wine glass",
}


class WarehouseClassMapper:
    """
    Standardized, rule-governed class mapper for CareGuard AI video intelligence.
    Enforces strict mapping boundaries between warehouse entities and generic COCO classes.
    """

    def __init__(
        self,
        person_conf_threshold: float = 0.25,
        product_conf_threshold: float = 0.15,
        pallet_conf_threshold: float = 0.25,
        mhe_conf_threshold: float = 0.25,
        other_conf_threshold: float = 0.35,
    ):
        self.person_conf_threshold = person_conf_threshold
        self.product_conf_threshold = product_conf_threshold
        self.pallet_conf_threshold = pallet_conf_threshold
        self.mhe_conf_threshold = mhe_conf_threshold
        self.other_conf_threshold = other_conf_threshold

    def map_category(self, label: str) -> WarehouseObjectCategory:
        """
        Maps an object detection label to a canonical warehouse category.
        Strictly prevents unrelated COCO items from being classified as PRODUCT.
        """
        if not label:
            return WarehouseObjectCategory.OTHER

        clean = label.lower().strip().replace("-", "_")

        if clean in PERSON_LABELS:
            return WarehouseObjectCategory.PERSON
        elif clean in PRODUCT_LABELS:
            return WarehouseObjectCategory.PRODUCT
        elif clean in PALLET_LABELS:
            return WarehouseObjectCategory.PALLET
        elif clean in MHE_LABELS:
            return WarehouseObjectCategory.MHE
        else:
            # All other classes (including cell phone, laptop, suitcase, backpack, chair, etc.)
            # are classified as OTHER and NEVER forced to PRODUCT/PACKAGE.
            return WarehouseObjectCategory.OTHER

    def get_confidence_threshold(self, category: WarehouseObjectCategory) -> float:
        """Returns the minimum confidence threshold required for a given warehouse category."""
        if category == WarehouseObjectCategory.PERSON:
            return self.person_conf_threshold
        elif category == WarehouseObjectCategory.PRODUCT:
            return self.product_conf_threshold
        elif category == WarehouseObjectCategory.PALLET:
            return self.pallet_conf_threshold
        elif category == WarehouseObjectCategory.MHE:
            return self.mhe_conf_threshold
        else:
            return self.other_conf_threshold

    def is_valid_confidence(self, label: str, confidence: float) -> bool:
        """Determines if a raw detection meets the minimum confidence threshold for its category."""
        category = self.map_category(label)
        threshold = self.get_confidence_threshold(category)
        return confidence >= threshold

    def get_display_label(
        self,
        category: WarehouseObjectCategory,
        raw_label: str = "",
        track_id: Optional[int] = None,
        mode: str = "clean",
        confidence: Optional[float] = None,
        carrying_state: Optional[str] = None,
    ) -> Tuple[str, Tuple[int, int, int]]:
        """
        Returns the formatted display label and BGR color tuple for HUD drawing.
        
        Colors (BGR):
          - PRODUCT: Emerald (70, 200, 100)
          - PERSON: Azure / Amber (255, 140, 30)
          - PALLET: Cyan / Sky (30, 180, 240)
          - MHE: Violet / Purple (200, 100, 240)
          - OTHER: Neutral Slate (150, 155, 160)
        """
        clean_raw = (raw_label or "object").upper().replace("_", " ")

        if category == WarehouseObjectCategory.PRODUCT:
            color = (70, 200, 100)
            base_name = "PRODUCT"
        elif category == WarehouseObjectCategory.PERSON:
            color = (255, 140, 30)
            base_name = "HANDLER"
        elif category == WarehouseObjectCategory.PALLET:
            color = (30, 180, 240)
            base_name = "PALLET"
        elif category == WarehouseObjectCategory.MHE:
            color = (200, 100, 240)
            base_name = "MHE"
        else:
            color = (150, 155, 160)
            base_name = clean_raw if clean_raw not in ("PACKAGE", "PRODUCT") else "OBJECT"

        if mode == "detection" and confidence is not None:
            text = f"{base_name} {int(confidence * 100)}%"
        elif track_id is not None:
            text = f"{base_name} #{track_id}"
            if carrying_state:
                text = f"{text} [{carrying_state}]"
        else:
            text = base_name
            if carrying_state:
                text = f"{text} [{carrying_state}]"

        return text, color
