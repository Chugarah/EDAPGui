"""
File: scripts/SunAvoidance.py

Description:
    Enhanced sun avoidance logic for the Elite Dangerous Autopilot.
    When the sun is detected directly ahead (obstructing the target),
    this script will pitch the ship away from the sun and continue
    flying in that direction for a configurable duration to ensure
    safe clearance before attempting to re-align to the target.

Author: EDAPGui Contributors
"""

import time
from EDlogger import logger


class SunAvoidance:
    """Handles sun avoidance maneuvers for the autopilot."""

    def __init__(self, ap_instance):
        """
        Initialize the SunAvoidance handler.
        
        Args:
            ap_instance: Reference to the main EDAutopilot instance for accessing
                         config, keys, screen regions, and other shared resources.
        """
        self.ap = ap_instance

    def execute(self, scr_reg) -> bool:
        """
        Execute the sun avoidance maneuver.
        
        This method:
        1. Checks if the sun is directly ahead (smart check with occlusion)
        2. Pitches up until the sun is no longer in front
        3. Continues flying away for the configured duration
        4. Returns control to the main navigation loop
        
        Args:
            scr_reg: Screen regions instance for sun detection.
            
        Returns:
            bool: True if avoidance was performed, False if sun was not detected.
        """
        # Smart Sun Detection Logic:
        # If the target is occluded (dotted line), we are likely grazing the sun.
        # In this case, we lower the threshold to strictly avoid ANY sun glare.
        is_occluded = self.ap.is_destination_occluded(scr_reg)

        # Default threshold is 5%, but if occluded, be super sensitive (1%)
        threshold = 1 if is_occluded else 5
        
        sun_percent = scr_reg.sun_percent(scr_reg.screen)
        
        if sun_percent <= threshold:
            logger.debug(f'SunAvoidance: Clear path (Sun: {sun_percent}%, Threshold: {threshold}%, Occluded: {is_occluded})')
            # If we are occluded but don't see the sun yet, we might still want to trigger 
            # if we are VERY close to the sun edge, but for now we trust the 1% threshold to catch the edge.
            return False

        logger.info(f'SunAvoidance: Sun detected! (Sun: {sun_percent}%, Threshold: {threshold}%, Occluded: {is_occluded})')
        self.ap.ap_ckb('log+vce', f'Sun detected ({sun_percent}%), avoiding...')

        # Get configuration values
        avoidance_duration = self.ap.config.get('SunAvoidanceDuration', 20)
        pitch_rate = self.ap.pitchrate
        sun_pitch_up_time = self.ap.sunpitchuptime

        # Calculate failsafe timeout (120 degrees of pitch + buffer)
        fail_safe_timeout = (120 / pitch_rate) + 3
        start_time = time.time()

        # Phase 1: Pitch up until sun is no longer directly ahead
        logger.debug('SunAvoidance: Phase 1 - Pitching away from sun')
        self.ap.keys.send('PitchUpButton', state=1)

        # We loop until sun_percent drops below the threshold (or 5% if we want to be less strict on exit, 
        # but sticking to threshold is safer).
        while True:
            current_sun = scr_reg.sun_percent(scr_reg.screen)
            if current_sun <= 5: # Use standard threshold for "clear enough" to stop pitching
                break

            # Check for interdiction during maneuver
            if self.ap.interdiction_check():
                self.ap.keys.send('PitchUpButton', state=0)
                self.ap.keys.send('SetSpeedZero')
                logger.warning('SunAvoidance: Interrupted by interdiction')
                return True

            # Failsafe: Don't pitch forever in bright star fields
            if (time.time() - start_time) > fail_safe_timeout:
                logger.warning('SunAvoidance: Failsafe timeout triggered (bright star field?)')
                break

            time.sleep(0.1)

        # Apply ship-specific pitch adjustment
        time.sleep(0.35)
        if sun_pitch_up_time > 0.0:
            time.sleep(sun_pitch_up_time)

        self.ap.keys.send('PitchUpButton', state=0)

        # Handle ships that run cool (need less pitch)
        if sun_pitch_up_time < 0.0:
            self.ap.keys.send('PitchDownButton', state=1)
            time.sleep(-1.0 * sun_pitch_up_time)
            self.ap.keys.send('PitchDownButton', state=0)

        # Phase 2: Continue flying away from sun for the configured duration
        logger.debug(f'SunAvoidance: Phase 2 - Flying away for {avoidance_duration} seconds')
        self.ap.ap_ckb('log', f'Flying away from sun for {avoidance_duration}s')

        # Set speed to 100% during avoidance
        self.ap.keys.send('SetSpeed100')

        # Wait for the avoidance duration, checking for interrupts
        avoidance_start = time.time()
        while (time.time() - avoidance_start) < avoidance_duration:
            # Check for interdiction during avoidance flight
            if self.ap.interdiction_check():
                logger.warning('SunAvoidance: Interrupted by interdiction during avoidance flight')
                return True

            # Check if we somehow ended up facing the sun again (unlikely but possible)
            # Use standard threshold here to avoid excessive jitter
            if scr_reg.sun_percent(scr_reg.screen) > 5:
                logger.debug('SunAvoidance: Sun re-detected, resuming pitch up')
                self.ap.keys.send('PitchUpButton', state=1)
                time.sleep(1.0)
                self.ap.keys.send('PitchUpButton', state=0)

            time.sleep(0.5)

        logger.info('SunAvoidance: Avoidance maneuver complete, resuming navigation')
        self.ap.ap_ckb('log+vce', 'Sun avoidance complete')

        # Reduce speed to 50% before re-aligning to avoid overshooting
        self.ap.keys.send('SetSpeed50')

        return True

    def _is_sun_blocking_path(self, scr_reg) -> bool:
        """
        Check if the sun is directly ahead, blocking our path.
        DEPRECATED: Use logic inside execute() instead.
        
        Args:
            scr_reg: Screen regions instance.
            
        Returns:
            bool: True if sun is blocking, False otherwise.
        """
        sun_brightness_percent = scr_reg.sun_percent(scr_reg.screen)
        threshold = 5  # Percentage threshold for sun detection
        return sun_brightness_percent > threshold
