import cv2
import os
import sys
import numpy as np

# Import production classes (assuming strict file structure)
import Screen_Regions
import Image_Templates

class StaticScreen:
    """ Mimics Screen.py but operates on a static image frame """
    def __init__(self, frame_bgr):
        self.frame = frame_bgr
        self.screen_height, self.screen_width = frame_bgr.shape[:2]
        # Calculate scale relative to reference 3440x1440
        # If image is small (likely a crop), assume 1.0 scale to preserve template detail
        if self.screen_width < 1920:
             self.scaleX = 1.0
             self.scaleY = 1.0
        else:
             self.scaleX = self.screen_width / 3440.0
             self.scaleY = self.screen_height / 1440.0
        
    def get_screen_region(self, rect, rgb=False):
        """ Returns the sub-image for the given rect [x1, y1, x2, y2] """
        x1, y1, x2, y2 = rect
        # Clamp to image bounds
        x1 = max(0, min(x1, self.screen_width))
        y1 = max(0, min(y1, self.screen_height))
        x2 = max(0, min(x2, self.screen_width))
        y2 = max(0, min(y2, self.screen_height))
        
        region = self.frame[y1:y2, x1:x2]
        
        if rgb:
            return cv2.cvtColor(region, cv2.COLOR_BGR2RGB)
        return region # Return BGR by default (matches Screen.get_screen_region(rgb=False))


def test_occlusion_logic(scr_reg, frame, path):
    """
    Simulate the is_destination_occluded logic from ED_AP.py and print diagnostics.
    
    This tests:
    1. Solid target match (target template) - VETO check
    2. Occluded target match (target_occluded template)
    3. Dashed circle shape detection (fallback)
    4. Final decision: occluded=True/False
    """
    print(f"\n{'='*60}")
    print(f"Testing: {os.path.basename(path)}")
    print(f"Frame size: {frame.shape[1]}x{frame.shape[0]}, Scale: {scr_reg.screen.scaleX:.3f}")
    print(f"{'='*60}")
    
    try:
        # ============ SOLID TARGET CHECK (VETO) ============
        print("\n[1] Solid Target Check (VETO)")
        _, (_, target_val_p1, _, _), _ = scr_reg.match_template_in_region('target', 'target')
        _, (_, target_val_x3, _, _), _ = scr_reg.match_template_in_region_x3('target', 'target')
        target_val = max(target_val_p1, target_val_x3)
        target_thresh = scr_reg.target_thresh
        target_visible = target_val >= target_thresh
        
        print(f"    target match (pass1): {target_val_p1:.4f}")
        print(f"    target match (x3):    {target_val_x3:.4f}")
        print(f"    target best:          {target_val:.4f} (thresh: {target_thresh:.2f})")
        print(f"    VETO active:          {'YES - Target VISIBLE' if target_visible else 'NO'}")
        
        # ============ OCCLUDED TARGET CHECK ============
        print("\n[2] Occluded Target Check (Template)")
        _, (_, occ_val_p1, _, _), _ = scr_reg.match_template_in_region('target_occluded', 'target_occluded')
        _, (_, occ_val_x3, _, _), _ = scr_reg.match_template_in_region_x3('target_occluded', 'target_occluded')
        occ_val = max(occ_val_p1, occ_val_x3)
        occ_thresh = scr_reg.target_occluded_thresh
        occ_template_detected = occ_val >= occ_thresh
        
        print(f"    target_occluded match (pass1): {occ_val_p1:.4f}")
        print(f"    target_occluded match (x3):    {occ_val_x3:.4f}")
        print(f"    target_occluded best:          {occ_val:.4f} (thresh: {occ_thresh:.2f})")
        print(f"    Template detects occluded:     {'YES' if occ_template_detected else 'NO'}")
        
        # ============ DASHED CIRCLE FALLBACK ============
        print("\n[3] Dashed Circle Fallback (Shape Detection)")
        circle_found = False
        circle_score = 0.0
        circle_info = {}
        if not occ_template_detected:
            circle_found, circle_score, circle_result, circle_info = scr_reg.detect_dashed_circle(
                'target_occluded',
                ring_score_thresh=0.40,
                min_gap_gain=0.1
            )
            print(f"    circle_found:   {circle_found}")
            print(f"    circle_score:   {circle_score:.3f}")
            print(f"    candidates:     {circle_info.get('candidates', 0)}")
            print(f"    coverage:       {circle_info.get('coverage', 0):.2f}")
            print(f"    runs:           {circle_info.get('runs', 0)}")
            print(f"    gap_gain:       {circle_info.get('gap_gain', 0):.3f}")
        else:
            print("    (Skipped - template already detected occlusion)")
        
        # ============ FINAL DECISION ============
        print("\n[4] Final Decision")
        if target_visible:
            final_occluded = False
            reason = "VETO: Solid target visible"
        elif occ_template_detected:
            final_occluded = True
            reason = "Template matched occluded target"
        elif circle_found:
            final_occluded = True
            reason = "Circle shape detected"
        else:
            final_occluded = False
            reason = "No occlusion detected"
        
        status = "[OCCLUDED]" if final_occluded else "[NOT OCCLUDED]"
        print(f"    {status} - {reason}")
        
        return final_occluded, target_val, occ_val, circle_score
        
    except Exception as e:
        print(f"    [ERROR] Template matching failed: {e}")
        print(f"    (Image may be too small or mismatched resolution)")
        return None, 0.0, 0.0, 0.0


def main():
    # Collect test images
    image_paths = []
    
    if len(sys.argv) > 1:
        image_paths = sys.argv[1:]
    else:
        # Default: scan both test/target-occluded and test/target directories
        test_dirs = [
            os.path.join(os.getcwd(), 'test', 'target-occluded'),
            os.path.join(os.getcwd(), 'test', 'target'),
        ]
        
        for test_dir in test_dirs:
            if os.path.exists(test_dir):
                print(f"Scanning: {test_dir}")
                for f in os.listdir(test_dir):
                    if f.lower().endswith(('.png', '.bmp', '.jpg')):
                        image_paths.append(os.path.join(test_dir, f))
        
        if not image_paths:
            print("No images found in test directories.")
            print("Usage: python Test_Routines.py [image1.png] [image2.png] ...")
            return

    print(f"\nFound {len(image_paths)} test image(s)\n")

    results = []
    
    for path in image_paths:
        if not os.path.exists(path):
            print(f"File not found: {path}")
            continue
            
        frame = cv2.imread(path)
        if frame is None:
             print(f"Could not load image: {path}")
             continue
        
        # Initialize environment
        static_screen = StaticScreen(frame)
        templ = Image_Templates.Image_Templates(static_screen.scaleX, static_screen.scaleY, static_screen.scaleX)
        scr_reg = Screen_Regions.Screen_Regions(static_screen, templ)
        
        # Run the occlusion test
        final_occluded, target_val, occ_val, circle_score = test_occlusion_logic(scr_reg, frame, path)
        
        results.append({
            'path': path,
            'occluded': final_occluded,
            'target_val': target_val,
            'occ_val': occ_val,
            'circle_score': circle_score
        })
        
        # Debug image (only if test succeeded)
        if final_occluded is not None:
            dbg = frame.copy()
            roi_rect = scr_reg.reg['target_occluded']['rect']
            color = (0, 0, 255) if final_occluded else (0, 255, 0)
            cv2.rectangle(dbg, (roi_rect[0], roi_rect[1]), (roi_rect[2], roi_rect[3]), color, 2)
            label = "OCCLUDED" if final_occluded else "CLEAR"
            cv2.putText(dbg, label, (roi_rect[0], roi_rect[1] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            out_name = f"test_result_{os.path.basename(path)}"
            cv2.imwrite(out_name, dbg)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        if r['occluded'] is None:
            status = "[ERROR]   "
        elif r['occluded']:
            status = "[OCCLUDED]"
        else:
            status = "[CLEAR]   "
        print(f"  {status} {os.path.basename(r['path']):<40} "
              f"target={r['target_val']:.3f} occ={r['occ_val']:.3f} circle={r['circle_score']:.3f}")


if __name__ == "__main__":
    main()

