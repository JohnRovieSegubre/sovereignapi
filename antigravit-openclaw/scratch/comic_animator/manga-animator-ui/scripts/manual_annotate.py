import cv2
import json
import argparse
from pathlib import Path
import logging

# MediaPipe Pose Landmarks
LANDMARK_NAMES = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer",
    "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear", "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
    "left_pinky", "right_pinky",
    "left_index", "right_index",
    "left_thumb", "right_thumb",
    "left_hip", "right_hip",
    "left_knee", "right_knee",
    "left_ankle", "right_ankle",
    "left_heel", "right_heel",
    "left_foot_index", "right_foot_index"
]

current_idx = 0
points = [] # List of (x, y) tuples. (-1, -1) for skipped.
img_display = None

def click_event(event, x, y, flags, param):
    global current_idx, points, img_display
    
    if event == cv2.EVENT_LBUTTONDOWN:
        if current_idx < len(LANDMARK_NAMES):
            points.append((x, y))
            current_idx += 1
            print(f"Set {LANDMARK_NAMES[current_idx-1]} at ({x}, {y})")

def main():
    global current_idx, img_display
    
    parser = argparse.ArgumentParser(description="Manual Landmark Annotator")
    parser.add_argument("image", help="Path to image file")
    parser.add_argument("label", help="Label for this image (e.g. 'start' or 'end')")
    parser.add_argument("--output", default="output/landmarks_override.json", help="Path to output JSON")
    args = parser.parse_args()
    
    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: Image {image_path} not found.")
        return

    output_path = Path(args.output)
    
    # Load existing overrides if any
    data = {}
    if output_path.exists():
        try:
            with open(output_path, "r") as f:
                data = json.load(f)
        except:
            data = {}

    img = cv2.imread(str(image_path))
    if img is None:
        print("Failed to load image.")
        return
        
    cv2.namedWindow("Annotator", cv2.WINDOW_NORMAL) # Allow resizing
    cv2.setMouseCallback("Annotator", click_event)
    
    print("\n--- INSTRUCTIONS ---")
    print("Click to place landmark.")
    print("SPACE: Skip current landmark.")
    print("z: Undo last point.")
    print("ESC: Quit without saving.")
    print("--------------------")

    while True:
        img_display = img.copy()
        
        # Draw all placed points
        for i, pt in enumerate(points):
            if pt != (-1, -1):
                cv2.circle(img_display, pt, 5, (0, 255, 0), -1)
                # cv2.putText(img_display, str(i), pt, cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                
        # Connect lines (skeleton preview) - rudimentary
        skeleton_pairs = [
            (11, 12), (11, 13), (13, 15), (12, 14), (14, 16), # Arms
            (11, 23), (12, 24), (23, 24), # Torso
            (23, 25), (25, 27), (24, 26), (26, 28) # Legs
        ]
        for idx1, idx2 in skeleton_pairs:
            if idx1 < len(points) and idx2 < len(points):
                p1 = points[idx1]
                p2 = points[idx2]
                if p1 != (-1, -1) and p2 != (-1, -1):
                    cv2.line(img_display, p1, p2, (0, 255, 255), 2)

        # Show current target
        if current_idx < len(LANDMARK_NAMES):
            msg = f"Click: {current_idx} - {LANDMARK_NAMES[current_idx]}"
            cv2.putText(img_display, msg, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        else:
            cv2.putText(img_display, "DONE! Press 's' to save or 'q' to quit.", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow("Annotator", img_display)
        key = cv2.waitKey(20) & 0xFF
        
        if key == 27: # ESC
            print("Quitting without save.")
            break
        elif key == ord('z'): # Undo
            if points:
                points.pop()
                current_idx -= 1
        elif key == 32: # Space - Skip
            if current_idx < len(LANDMARK_NAMES):
                print(f"Skipped {LANDMARK_NAMES[current_idx]}")
                points.append((-1, -1))
                current_idx += 1
        elif key == ord('s'):
            if current_idx >= len(LANDMARK_NAMES):
                # Save
                # Handle skipped points? 
                # For this pipeline, we just save what we have. 
                # But pipeline expects x,y. (-1,-1) might break normalization?
                # We will save (-1,-1) and let keypoints.py handle or error? 
                # Actually, keypoints.py just transforms by w/h. (-1/w) is valid but off-screen.
                
                # Check for skipped points logic in main pipeline later. 
                # Ideally manual annotation implies we want them all or robust interpolation.
                
                data[args.label] = points
                with open(output_path, "w") as f:
                    json.dump(data, f, indent=2)
                print(f"Saved overrides to {output_path}")
                break
        elif key == ord('q'):
             break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
