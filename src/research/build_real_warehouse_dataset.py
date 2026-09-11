"""
Build the complete real warehouse dataset for YOLO26n transfer learning.
Directory: data/datasets/warehouse_real_v2/
Taxonomy:
0: person
1: product
2: pallet
3: mhe
"""
import os
import shutil
import glob
import json
import urllib.request
import cv2
import numpy as np

BASE_DIR = 'data/datasets/warehouse_real_v2'
TRAIN_IMG = os.path.join(BASE_DIR, 'images', 'train')
VAL_IMG = os.path.join(BASE_DIR, 'images', 'val')
TEST_IMG = os.path.join(BASE_DIR, 'images', 'test')

TRAIN_LBL = os.path.join(BASE_DIR, 'labels', 'train')
VAL_LBL = os.path.join(BASE_DIR, 'labels', 'val')
TEST_LBL = os.path.join(BASE_DIR, 'labels', 'test')

for d in [TRAIN_IMG, VAL_IMG, TEST_IMG, TRAIN_LBL, VAL_LBL, TEST_LBL]:
    os.makedirs(d, exist_ok=True)

# Import annotation generator
import sys
sys.path.append('src/research')
from generate_warehouse_annotations import get_annotations_for_frame, xyxy_to_yolo, CLASS_MAP

def process_warehouse_frames():
    """Populate warehouse video frames into train, val, test."""
    raw_frames = sorted(glob.glob('data/datasets/warehouse_real_v2/raw_frames/*.jpg'))
    print(f"[1/4] Processing {len(raw_frames)} warehouse video frames...")
    
    counts = {'train': 0, 'val': 0, 'test': 0}
    for idx, fpath in enumerate(raw_frames):
        # Sequence split:
        # 0-11: Normal staging -> train
        # 12-29: Dragging -> val
        # 30-43: Throwing -> test (held-out)
        # 44-59: Rolling / Stacking -> train
        if 0 <= idx <= 11 or 44 <= idx <= 59:
            split = 'train'
            img_dest = TRAIN_IMG
            lbl_dest = TRAIN_LBL
        elif 12 <= idx <= 29:
            split = 'val'
            img_dest = VAL_IMG
            lbl_dest = VAL_LBL
        else: # 30 <= idx <= 43
            split = 'test'
            img_dest = TEST_IMG
            lbl_dest = TEST_LBL
            
        counts[split] += 1
        fname = os.path.basename(fpath)
        base_name = os.path.splitext(fname)[0]
        
        # Copy image
        shutil.copy(fpath, os.path.join(img_dest, fname))
        
        # Generate labels
        objs = get_annotations_for_frame(idx)
        img = cv2.imread(fpath)
        h, w, _ = img.shape
        lines = []
        for obj_name, box in objs.items():
            cls_id = CLASS_MAP[obj_name]
            yolo_box = xyxy_to_yolo(box, w, h)
            lines.append(f"{cls_id} {yolo_box[0]:.6f} {yolo_box[1]:.6f} {yolo_box[2]:.6f} {yolo_box[3]:.6f}")
            
        with open(os.path.join(lbl_dest, f"{base_name}.txt"), 'w') as f:
            f.write('\n'.join(lines) + '\n')
            
    print(f"  Warehouse frames split: {counts}")

def download_photographic_boxes():
    """Download real photographic cardboard box images and convert class 0 -> 1 (PRODUCT)."""
    print("[2/4] Downloading real photographic cardboard box images...")
    
    # We will fetch test and valid images from qadeersan/ML-Pallet-Box-Counter
    repo_api = "https://api.github.com/repos/qadeersan/ML-Pallet-Box-Counter/contents/Final_Object_Detection.v1i.yolov8"
    req = urllib.request.Request(f"{repo_api}/valid/images", headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req) as r:
            valid_items = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f"  Error fetching image list: {e}")
        return

    # Select 80 diverse images: 50 train, 15 val, 15 test
    selected_items = valid_items[:80]
    raw_label_base = "https://raw.githubusercontent.com/qadeersan/ML-Pallet-Box-Counter/main/Final_Object_Detection.v1i.yolov8/valid/labels"
    
    counts = {'train': 0, 'val': 0, 'test': 0}
    for i, it in enumerate(selected_items):
        if i < 50:
            split = 'train'
            img_dir, lbl_dir = TRAIN_IMG, TRAIN_LBL
        elif i < 65:
            split = 'val'
            img_dir, lbl_dir = VAL_IMG, VAL_LBL
        else:
            split = 'test'
            img_dir, lbl_dir = TEST_IMG, TEST_LBL
            
        img_name = it['name']
        lbl_name = os.path.splitext(img_name)[0] + '.txt'
        
        # Download image
        img_save_name = f"carton_real_{i:03d}.jpg"
        lbl_save_name = f"carton_real_{i:03d}.txt"
        
        urllib.request.urlretrieve(it['download_url'], os.path.join(img_dir, img_save_name))
        
        # Download label and remap class 0 (box) -> 1 (PRODUCT)
        lbl_url = f"{raw_label_base}/{lbl_name}"
        try:
            req_l = urllib.request.Request(lbl_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req_l) as lr:
                raw_lines = lr.read().decode('utf-8').strip().splitlines()
                remapped = []
                for line in raw_lines:
                    parts = line.strip().split()
                    if parts:
                        # Remap class 0 -> 1 (PRODUCT)
                        parts[0] = '1'
                        remapped.append(' '.join(parts))
                with open(os.path.join(lbl_dir, lbl_save_name), 'w') as lf:
                    lf.write('\n'.join(remapped) + '\n')
            counts[split] += 1
        except Exception as e:
            print(f"  Warning downloading label {lbl_name}: {e}")
            
    print(f"  Photographic boxes downloaded: {counts}")

def process_webcam_and_negatives():
    """Add user webcam captures and create realistic box-in-webcam samples and negative background samples."""
    print("[3/4] Processing webcam frames and negative background samples...")
    
    # 1. User webcam images (person only)
    webcam_files = sorted(glob.glob('data/datasets/webcam_captures/*.jpg'))
    # In webcam_box_00 to 07, user is at [110, 190, 540, 480] in 640x480
    for idx, fpath in enumerate(webcam_files):
        img = cv2.imread(fpath)
        h, w, _ = img.shape
        split = 'train' if idx < 6 else 'val'
        img_dir = TRAIN_IMG if split == 'train' else VAL_IMG
        lbl_dir = TRAIN_LBL if split == 'train' else VAL_LBL
        
        out_name = f"webcam_user_{idx:02d}.jpg"
        shutil.copy(fpath, os.path.join(img_dir, out_name))
        
        # Person annotation: [110, 180, 540, 480]
        yolo_box = xyxy_to_yolo([110, 180, 540, 480], w, h)
        with open(os.path.join(lbl_dir, f"webcam_user_{idx:02d}.txt"), 'w') as f:
            f.write(f"0 {yolo_box[0]:.6f} {yolo_box[1]:.6f} {yolo_box[2]:.6f} {yolo_box[3]:.6f}\n")
            
    # 2. Pure negative background samples (0 labels)
    # Extract background crops from webcam images (upper half: wall, shelf, curtains)
    for idx in range(10):
        split = 'train' if idx < 6 else ('val' if idx < 8 else 'test')
        img_dir = TRAIN_IMG if split == 'train' else (VAL_IMG if split == 'val' else TEST_IMG)
        lbl_dir = TRAIN_LBL if split == 'train' else (VAL_LBL if split == 'val' else TEST_LBL)
        
        # Load webcam frame and crop empty upper portion or blur out person
        base_img = cv2.imread(webcam_files[idx % len(webcam_files)])
        neg_img = base_img.copy()
        # Crop the upper room section (curtains, shelf, wall) and resize to 640x480
        neg_crop = neg_img[0:300, 0:640]
        neg_resized = cv2.resize(neg_crop, (640, 480))
        
        out_name = f"bg_negative_{idx:02d}.jpg"
        cv2.imwrite(os.path.join(img_dir, out_name), neg_resized)
        
        # Empty label file
        with open(os.path.join(lbl_dir, f"bg_negative_{idx:02d}.txt"), 'w') as f:
            f.write("")
            
    # 3. Realistic Box-in-Webcam images:
    # Take real cardboard box crops from downloaded carton images and place them realistically
    # in front of the webcam background (on table, held by user)
    carton_images = sorted(glob.glob(os.path.join(TRAIN_IMG, 'carton_real_*.jpg')))
    if carton_images:
        print("  Generating realistic box-in-webcam samples...")
        for k in range(20):
            split = 'train' if k < 12 else ('val' if k < 16 else 'test')
            img_dir = TRAIN_IMG if split == 'train' else (VAL_IMG if split == 'val' else TEST_IMG)
            lbl_dir = TRAIN_LBL if split == 'train' else (VAL_LBL if split == 'val' else TEST_LBL)
            
            webcam_bg = cv2.imread(webcam_files[k % len(webcam_files)]).copy()
            carton_src = cv2.imread(carton_images[k % len(carton_images)])
            
            # Crop center region of carton
            ch, cw, _ = carton_src.shape
            box_crop = carton_src[int(ch*0.1):int(ch*0.9), int(cw*0.1):int(cw*0.9)]
            
            # Vary placement: center desk, left desk, right desk
            target_w = np.random.randint(140, 240)
            aspect = float(box_crop.shape[0]) / max(1.0, float(box_crop.shape[1]))
            target_h = int(min(180, target_w * aspect))
            target_w = max(50, target_w)
            target_h = max(50, target_h)
            resized_box = cv2.resize(box_crop, (target_w, target_h))
            
            # Place in lower half of webcam frame (desk / lap level)
            max_x = max(60, 640 - target_w - 10)
            pos_x = np.random.randint(20, max_x)
            max_y = max(250, 480 - target_h)
            min_y = min(220, max_y - 10)
            pos_y = np.random.randint(min_y, max_y)
            
            # Blend smoothly into webcam background
            webcam_bg[pos_y:pos_y+target_h, pos_x:pos_x+target_w] = resized_box
            
            out_name = f"webcam_box_scene_{k:02d}.jpg"
            cv2.imwrite(os.path.join(img_dir, out_name), webcam_bg)
            
            # Labels: Person + Product
            wh, ww, _ = webcam_bg.shape
            person_yolo = xyxy_to_yolo([110, 180, 540, 480], ww, wh)
            box_yolo = xyxy_to_yolo([pos_x, pos_y, pos_x + target_w, pos_y + target_h], ww, wh)
            
            with open(os.path.join(lbl_dir, f"webcam_box_scene_{k:02d}.txt"), 'w') as f:
                f.write(f"0 {person_yolo[0]:.6f} {person_yolo[1]:.6f} {person_yolo[2]:.6f} {person_yolo[3]:.6f}\n")
                f.write(f"1 {box_yolo[0]:.6f} {box_yolo[1]:.6f} {box_yolo[2]:.6f} {box_yolo[3]:.6f}\n")

def create_yaml_config():
    """Create data.yaml for YOLO26 training."""
    print("[4/4] Creating data.yaml...")
    yaml_content = f"""# Warehouse Perception Real Dataset v2 (Godrej CareGuard AI)
path: {os.path.abspath(BASE_DIR).replace('\\', '/')}
train: images/train
val: images/val
test: images/test

nc: 4
names:
  0: person
  1: product
  2: pallet
  3: mhe
"""
    yaml_path = os.path.join(BASE_DIR, 'data.yaml')
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)
    print(f"  data.yaml created at {yaml_path}")

def print_summary():
    """Print dataset statistics."""
    for split in ['train', 'val', 'test']:
        img_dir = os.path.join(BASE_DIR, 'images', split)
        lbl_dir = os.path.join(BASE_DIR, 'labels', split)
        imgs = glob.glob(os.path.join(img_dir, '*.jpg'))
        lbls = glob.glob(os.path.join(lbl_dir, '*.txt'))
        
        # Count classes
        class_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        empty_lbls = 0
        for lp in lbls:
            with open(lp, 'r') as f:
                content = f.read().strip()
                if not content:
                    empty_lbls += 1
                    continue
                for line in content.splitlines():
                    parts = line.strip().split()
                    if parts:
                        cls_id = int(parts[0])
                        class_counts[cls_id] = class_counts.get(cls_id, 0) + 1
                        
        print(f"\n--- Split: {split.upper()} ---")
        print(f"  Images: {len(imgs)}, Labels: {len(lbls)} (Negative samples: {empty_lbls})")
        print(f"  Classes: PERSON(0)={class_counts[0]}, PRODUCT(1)={class_counts[1]}, PALLET(2)={class_counts[2]}, MHE(3)={class_counts[3]}")

def main():
    process_warehouse_frames()
    download_photographic_boxes()
    process_webcam_and_negatives()
    create_yaml_config()
    print_summary()

if __name__ == '__main__':
    main()
