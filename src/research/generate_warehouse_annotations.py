"""
Generate and visually verify bounding box annotations for real warehouse video frames.
Taxonomy:
0: person
1: product
2: pallet
3: mhe
"""
import cv2
import os
import glob
import numpy as np

def interpolate_box(box_a, box_b, alpha):
    """Linearly interpolate between two boxes [x1, y1, x2, y2]."""
    return [
        box_a[i] + (box_b[i] - box_a[i]) * alpha
        for i in range(4)
    ]

def xyxy_to_yolo(box, img_w=1280, img_h=720):
    """Convert [x1, y1, x2, y2] to YOLO normalized [x_center, y_center, width, height]."""
    x1, y1, x2, y2 = box
    x1 = max(0.0, min(float(img_w), float(x1)))
    x2 = max(0.0, min(float(img_w), float(x2)))
    y1 = max(0.0, min(float(img_h), float(y1)))
    y2 = max(0.0, min(float(img_h), float(y2)))
    
    w = x2 - x1
    h = y2 - y1
    xc = x1 + w / 2.0
    yc = y1 + h / 2.0
    
    return [xc / img_w, yc / img_h, w / img_w, h / img_h]

# Keyframe definitions: frame_idx -> dict of object_name -> [x1, y1, x2, y2]
KEYFRAMES = {
    0: {
        'person': [820, 290, 965, 560],
        'pallet': [525, 475, 830, 585],
    },
    5: {
        'person': [800, 290, 930, 500],
        'pallet': [525, 480, 830, 590],
        'product': [660, 360, 980, 540],
    },
    10: {
        'person': [760, 290, 880, 500],
        'pallet': [150, 640, 450, 720],
        'product': [640, 360, 980, 540],
        'mhe': [730, 600, 910, 715],
    },
    16: {
        'person': [830, 280, 960, 520],
        'product': [660, 360, 980, 540],
        'mhe': [730, 600, 910, 715],
    },
    20: {
        'person': [900, 265, 1030, 535],
        'product': [660, 360, 980, 540],
        'mhe': [730, 600, 910, 715],
    },
    26: {
        'person': [850, 265, 980, 520],
        'product': [670, 340, 990, 530],
        'mhe': [730, 600, 910, 715],
    },
    32: {
        'person': [795, 265, 920, 510],
        'product': [680, 320, 1010, 520],
        'mhe': [730, 600, 910, 715],
    },
    35: {
        'person': [630, 225, 745, 475],
        'product': [700, 280, 1050, 500],
        'mhe': [730, 600, 910, 715],
    },
    40: {
        'person': [765, 190, 915, 450],
        'product': [700, 170, 1080, 300],
        'product_stack': [680, 260, 1060, 480],
        'mhe': [730, 600, 910, 715],
    },
    45: {
        'person': [765, 200, 920, 460],
        'product': [680, 230, 1070, 420],
        'product_stack': [680, 260, 1060, 480],
        'mhe': [730, 600, 910, 715],
    },
    50: {
        'person': [765, 215, 935, 475],
        'product': [650, 240, 1050, 470],
        'mhe': [730, 600, 910, 715],
    },
    59: {
        'person': [765, 215, 935, 475],
        'product': [650, 240, 1050, 470],
        'mhe': [730, 600, 910, 715],
    },
}

def get_annotations_for_frame(idx):
    """Interpolate annotations for frame idx from keyframes."""
    kf_indices = sorted(KEYFRAMES.keys())
    
    # Find bounding keyframes
    if idx <= kf_indices[0]:
        return KEYFRAMES[kf_indices[0]]
    if idx >= kf_indices[-1]:
        return KEYFRAMES[kf_indices[-1]]
    
    k_prev = kf_indices[0]
    k_next = kf_indices[-1]
    for k in kf_indices:
        if k <= idx:
            k_prev = k
        if k >= idx:
            k_next = k
            break
            
    if k_prev == k_next:
        return KEYFRAMES[k_prev]
        
    alpha = (idx - k_prev) / float(k_next - k_prev)
    prev_objs = KEYFRAMES[k_prev]
    next_objs = KEYFRAMES[k_next]
    
    interpolated = {}
    all_keys = set(prev_objs.keys()).union(set(next_objs.keys()))
    for key in all_keys:
        if key in prev_objs and key in next_objs:
            interpolated[key] = interpolate_box(prev_objs[key], next_objs[key], alpha)
        elif key in prev_objs and alpha < 0.5:
            interpolated[key] = prev_objs[key]
        elif key in next_objs and alpha >= 0.5:
            interpolated[key] = next_objs[key]
            
    return interpolated

CLASS_MAP = {
    'person': 0,
    'product': 1,
    'product_stack': 1,
    'pallet': 2,
    'mhe': 3,
}

COLORS = {
    0: (255, 100, 0),    # Person: Blue-ish
    1: (0, 220, 0),      # Product: Green
    2: (0, 165, 255),    # Pallet: Orange
    3: (200, 50, 200),   # MHE: Magenta
}

NAMES = {
    0: 'PERSON',
    1: 'PRODUCT',
    2: 'PALLET',
    3: 'MHE',
}

def main():
    raw_frames = sorted(glob.glob('data/datasets/warehouse_real_v2/raw_frames/*.jpg'))
    out_annot_dir = 'data/research/annotated_verification'
    os.makedirs(out_annot_dir, exist_ok=True)
    
    all_labels = {}
    print(f"Generating annotations for {len(raw_frames)} warehouse frames...")
    
    for idx, fpath in enumerate(raw_frames):
        img = cv2.imread(fpath)
        h, w, _ = img.shape
        objs = get_annotations_for_frame(idx)
        
        yolo_lines = []
        vis_img = img.copy()
        
        for name, box in objs.items():
            cls_id = CLASS_MAP[name]
            yolo_box = xyxy_to_yolo(box, w, h)
            yolo_lines.append(f"{cls_id} {yolo_box[0]:.6f} {yolo_box[1]:.6f} {yolo_box[2]:.6f} {yolo_box[3]:.6f}")
            
            # Draw on verification image
            x1, y1, x2, y2 = [int(v) for v in box]
            color = COLORS[cls_id]
            label = f"{NAMES[cls_id]}"
            cv2.rectangle(vis_img, (x1, y1), (x2, y2), color, 2)
            cv2.putText(vis_img, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
        fname = os.path.basename(fpath)
        all_labels[fname] = yolo_lines
        
        # Save sample verification images
        if idx in [0, 5, 10, 16, 20, 26, 32, 35, 40, 45, 50, 58]:
            out_vis = os.path.join(out_annot_dir, f"vis_{idx:02d}_{fname}")
            cv2.imwrite(out_vis, vis_img)
            
    print(f"Done! Verified frames saved to {out_annot_dir}")
    print(f"Sample yolo lines for frame 10: {all_labels[os.path.basename(raw_frames[10])]}")

if __name__ == '__main__':
    main()
