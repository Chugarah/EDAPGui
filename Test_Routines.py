import cv2
import os
import sys
import time
import numpy as np

# Import production classes
import Screen_Regions
import Image_Templates
import Screen

class DummyCallback:
    """ Mock callback for Screen class logging """
    def __call__(self, event, msg):
        # Only print errors or interesting events to avoid spam
        if "ERROR" in msg:
            print(f"[Screen] {msg}")

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


def test_occlusion_logic(scr_reg, frame, path="Live Capture"):
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


# Mock classes for OCR dependency
class MockOCR:
    def __init__(self):
        pass
    def image_simple_ocr(self, image):
        # This is a stub. In a real test we'd need to properly mock or use the real OCR.
        # For now, we return a dummy string if the image looks like it might have text,
        # or we could instantiate the real OCR if available.
        try:
           import OCR
           # We need a screen object for OCR init, but it just stores it.
           # Let's try to verify if we can check 'sc_disengage_active' logic logic
           return None
        except:
           return None
           
    def string_similarity(self, s1, s2):
        return 0.0

class MockStatus:
    def get_flag2(self, flag): return False
    def get_flag(self, flag): return False

class MockAP:
    def __init__(self, screen):
        self.scr = screen
        self.config = {'SupercruiseAvoidanceCooldownSeconds': 5.0}
        self.locale = {"PRESS_TO_DISENGAGE_MSG": "PRESS [J] TO DISENGAGE"}
        try:
            import OCR
            self.ocr = OCR.OCR(screen)
        except Exception as e:
            print(f"[WARN] OCR init failed in test: {e}")
            self.ocr = MockOCR()
            
        self.debug_overlay = False
        self.cv_view = False

    def sc_disengage_active(self, scr_reg) -> bool:
        """ Copied logic from ED_AP.py sc_disengage_active for testing """
        # logic from ED_AP.py
        rect = scr_reg.reg['disengage']['rect']
        image = self.scr.get_screen_region(rect)
        # Fix color space issue mentioned in source
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        mask = scr_reg.capture_region_filtered(self.scr, 'disengage')
        masked_image = cv2.bitwise_and(image, image, mask=mask)
        
        # We process 'masked_image' for OCR
        # OCR the selected item
        sim_match = 0.35  # Similarity match 0.0 - 1.0
        sim = 0.0
        
        ocr_textlist = self.ocr.image_simple_ocr(masked_image)
        if ocr_textlist is not None:
            # We compare against the list string representation as done in ED_AP.py
            # "sim = self.ocr.string_similarity(self.locale[\"PRESS_TO_DISENGAGE_MSG\"], str(ocr_textlist))"
            sim = self.ocr.string_similarity(self.locale["PRESS_TO_DISENGAGE_MSG"], str(ocr_textlist))
            # print(f"    [OCR] Text: {ocr_textlist}, Sim: {sim:.3f}")

        return sim > sim_match, sim, ocr_textlist


def test_disengage_logic(scr_reg, frame, path="Live Capture"):
    """
    Test the 'Press [J] to Disengage' detection.
    Checks:
    1. Template Match (sc_disengage_label_up)
    2. OCR Match (sc_disengage_active) - The "Primary" check in modern ED_AP
    """
    print(f"\n{'='*60}")
    print(f"Testing Disengage: {os.path.basename(path)}")
    print(f"{'='*60}")

    try:
        # 1. Template Match (Legacy/Trigger)
        detected_template = False
        disengage_val = 0.0
        
        # Handle small images (crops) logic for template match
        if frame.shape[1] < 1000:
            # print("    [INFO] Small image detected - treating as pre-cropped region.")
            # Manual filter match
            filtered = scr_reg.filter_by_color(frame, scr_reg.blue_sco_color_range)
            templ_img = scr_reg.templates.template['disengage']['image']
            
            if filtered.shape[0] >= templ_img.shape[0] and filtered.shape[1] >= templ_img.shape[1]:
                match = cv2.matchTemplate(filtered, templ_img, cv2.TM_CCOEFF_NORMED)
                (_, disengage_val, _, _) = cv2.minMaxLoc(match)
        else:
            # Standard region
            _, (_, disengage_val, _, _), _ = scr_reg.match_template_in_region('disengage', 'disengage')
        
        thresh = scr_reg.disengage_thresh
        detected_template = disengage_val >= thresh
        
        print(f"    [Template] Match Score: {disengage_val:.4f} (thresh: {thresh:.2f}) -> {'YES' if detected_template else 'NO'}")

        # 2. OCR Match (Active Check)
        # We need an instance of a MockAP to run the logic or copy it here.
        # Since we initialized MockAP with the screen, we can use it.
        # Note: OCR requires the full screen object to grab regions if not provided directly,
        # but our MockAP uses self.scr.get_screen_region(rect).
        
        # If frame is small, we can't easily run the standard region logic without mocking get_screen_region
        # but for Live/Full screenshots it works.
        
        detected_ocr = False
        sim = 0.0
        text = ""
        
        if frame.shape[1] >= 1000:
            mock_ap = MockAP(scr_reg.screen)
            detected_ocr, sim, text = mock_ap.sc_disengage_active(scr_reg)
            print(f"    [OCR]      Similarity:  {sim:.4f} (thresh: 0.35) -> {'YES' if detected_ocr else 'NO'}")
            print(f"    [OCR]      Found Text:  {text}")
        else:
            print("    [OCR]      Skipped (Image too small/cropped for full coordinate lookup)")

        return (detected_template or detected_ocr), disengage_val
        
    except Exception as e:
        print(f"    [ERROR] Disengage check failed: {e}")
        import traceback
        traceback.print_exc()
        return None, 0.0


def run_live_test(test_mode='occlusion'):
    """ Run the specified test in a live loop using screen capture. """
    print("Initializing Live Screen Capture...")
    print("Press 'q' to quit.")
    
    cb = DummyCallback()
    try:
        screen = Screen.Screen(cb)
    except Exception as e:
        print(f"Failed to initialize Screen: {e}")
        return

    templ = Image_Templates.Image_Templates(screen.scaleX, screen.scaleY, screen.scaleX)
    scr_reg = Screen_Regions.Screen_Regions(screen, templ)
    
    while True:
        start_time = time.time()
        
        # 1. Capture full screen (for visualization context)
        frame = screen.get_screen_full()
        if frame is None:
            print("Failed to capture screen.")
            time.sleep(1)
            continue
            
        disp_frame = frame.copy() # Copy for drawing
            
        # 2. Run Logic & Visualization
        
        # --- OCCLUSION TEST ---
        if test_mode in ['occlusion', 'all']:
            final_occluded, target_val, occ_val, circle_score = test_occlusion_logic(scr_reg, frame, "Live Stream")
            
            # Draw ROI and Status
            roi_rect = scr_reg.reg['target_occluded']['rect'] # [x1, y1, x2, y2]
            color = (0, 0, 255) if final_occluded else (0, 255, 0)
            cv2.rectangle(disp_frame, (roi_rect[0], roi_rect[1]), (roi_rect[2], roi_rect[3]), color, 2)
            
            label = "OCCLUDED" if final_occluded else "CLEAR"
            text = f"{label} (T:{target_val:.2f} O:{occ_val:.2f} C:{circle_score:.2f})"
            cv2.putText(disp_frame, text, (roi_rect[0], roi_rect[1] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # --- DISENGAGE TEST ---
        if test_mode in ['disengage', 'all']:
            detected, val = test_disengage_logic(scr_reg, frame, "Live Stream")
            
            # Draw ROI and Status
            roi_rect = scr_reg.reg['disengage']['rect']
            color = (0, 255, 0) if detected else (0, 0, 255) # Green if found
            cv2.rectangle(disp_frame, (roi_rect[0], roi_rect[1]), (roi_rect[2], roi_rect[3]), color, 2)
            
            label = "DISENGAGE" if detected else "NO MATCH"
            text = f"{label} ({val:.2f})"
            # Draw text slightly below or above depending on region position to avoid overlap if running 'all'
            # Disengage is usually lower screen, Occclusion is center.
            cv2.putText(disp_frame, text, (roi_rect[0], roi_rect[1] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        
        # Resize for display if 4k
        final_display = disp_frame
        if disp_frame.shape[1] > 1920:
            scale = 1920 / disp_frame.shape[1]
            final_display = cv2.resize(disp_frame, None, fx=scale, fy=scale)
            
        cv2.imshow("Live Test Debug", final_display)
        
        # FPS control
        dt = time.time() - start_time
        wait_ms = max(1, int(100 - (dt * 1000))) # Cap at ~10 FPS
        
        key = cv2.waitKey(wait_ms) & 0xFF
        if key == ord('q'):
            break
            
    cv2.destroyAllWindows()


def main():
    # Parse arguments
    import argparse
    parser = argparse.ArgumentParser(description="Test EDAP Logic")
    parser.add_argument('images', metavar='IMG', type=str, nargs='*', 
                        help='Image files to test (offline mode)')
    parser.add_argument('--live', action='store_true', 
                        help='Force live capture mode (default if no images provided)')
    parser.add_argument('--test', choices=['occlusion', 'disengage', 'all'], default='occlusion',
                        help='Which test suite to run')
    
    args = parser.parse_args()
    
    # Decide mode
    if args.live or not args.images:
        run_live_test(args.test)
        return

    # Offline Mode
    image_paths = args.images
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
        
        disp_frame = frame.copy()
        
        # --- OCCLUSION TEST ---
        if args.test in ['occlusion', 'all']:
            final_occluded, target_val, occ_val, circle_score = test_occlusion_logic(scr_reg, frame, path)
            
            # Visualize
            roi_rect = scr_reg.reg['target_occluded']['rect']
            color = (0, 0, 255) if final_occluded else (0, 255, 0)
            cv2.rectangle(disp_frame, (roi_rect[0], roi_rect[1]), (roi_rect[2], roi_rect[3]), color, 2)
            label = "OCCLUDED" if final_occluded else "CLEAR"
            cv2.putText(disp_frame, label, (roi_rect[0], roi_rect[1] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            results.append({
                'path': path,
                'test': 'occlusion',
                'result': final_occluded,
                'details': f"target={target_val:.2f} occ={occ_val:.2f} circle={circle_score:.2f}"
            })

        # --- DISENGAGE TEST ---
        if args.test in ['disengage', 'all']:
            detected, val = test_disengage_logic(scr_reg, frame, path)
            
             # Visualize
            roi_rect = scr_reg.reg['disengage']['rect']
            color = (0, 255, 0) if detected else (0, 0, 255)
            cv2.rectangle(disp_frame, (roi_rect[0], roi_rect[1]), (roi_rect[2], roi_rect[3]), color, 2)
            label = "DISENGAGE" if detected else "NO MATCH"
            cv2.putText(disp_frame, label, (roi_rect[0], roi_rect[1] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            results.append({
                'path': path,
                'test': 'disengage',
                'result': detected,
                'details': f"score={val:.2f}"
            })

        # Save result image
        out_name = f"test_result_{os.path.basename(path)}"
        cv2.imwrite(out_name, disp_frame)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        res_str = str(r['result'])
        print(f"  [{r['test'].upper()}] {os.path.basename(r['path']):<30} {res_str:<10} {r['details']}")


if __name__ == "__main__":
    main()

