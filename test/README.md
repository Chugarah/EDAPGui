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
   # Run all default tests (occlusion) on images in test folders
   python Test_Routines.py

   # Run a specific test suite (e.g., disengage) on a specific image
   python Test_Routines.py "test/disengage/my_screenshot.png" --test disengage

   # Run live capture mode (continuously tests against main screen)
   python Test_Routines.py --live

   # Run live capture checking for specific criteria
   python Test_Routines.py --live --test disengage
   ```
   
   ### Command Line Arguments
   - `--live`: Force live screen capture mode (default if no images provided).
   - `--test {occlusion,disengage,all}`: Select which test logic to run (default: occlusion).
   
   Results (PASS/FAIL + Debug Statistics) will be printed to the console.
   Debug images showing the detection verification will be saved in the `EDAPGui` root folder with the prefix `test_result_`.

## Adding New Tests
Simply add new screenshot images to the relevant subfolder (e.g., `test/target-occluded`). The test script picks them up automatically.