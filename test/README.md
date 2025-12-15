# Test Suite

This directory contains test images organized by feature type.

## Folder Structure
- `target-occluded/`: Images for testing the dashed-circle occlusion detector.
- `compass/`: Images for compass recognition.
- `disengage/`: Images for supercruise disengage prompt detection.
- `navpoint/`: Images for navigation target alignment.

## Running Tests
To run the automated tests using the images in these folders:

1. Activate the environment:
   ```cmd
   conda activate EdapGui
   ```

2. Run the test routine:
   ```cmd
   python Test_Routines.py
   ```
   
   This will automatically scan `test/target-occluded` for common image files (`.png`, `.bmp`, `.jpg`) and run the dashed circle detector on them.
   
   Results (PASS/FAIL + Debug Statistics) will be printed to the console.
   Debug images showing the detection verification will be saved in the `EDAPGui` root folder with the prefix `test_result_`.

## Adding New Tests
Simply add new screenshot images to the relevant subfolder (e.g., `test/target-occluded`). The test script picks them up automatically.