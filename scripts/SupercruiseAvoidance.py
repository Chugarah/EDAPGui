"""
SupercruiseAvoidance.py - Planetary/Station Obstruction Avoidance for Supercruise

This script handles the scenario where the target (station/planet) is occluded
by another celestial body during Supercruise navigation. It performs a repositioning
maneuver to fly around the obstruction using compass-based escape heading.

Key behavior:
- Stage A: Acquire escape heading by pitching until compass shows destination at bottom AND behind
- Stage B: Fly away for guaranteed duration (no early exit based on occlusion state)
- Fallback: If compass unreliable, yaw 180° and pitch up

Author: EDAPGui Contributors
"""

import time
import math
from EDlogger import logging

logger = logging.getLogger(__name__)

# Threshold for detecting a star ahead (same as is_sun_dead_ahead)
SUN_BRIGHTNESS_THRESHOLD = 5

# Minimum confidence thresholds for compass/navpoint detection
COMPASS_CONFIDENCE_THRESHOLD = 0.4
NAVPOINT_CONFIDENCE_THRESHOLD = 0.4


class SupercruiseAvoidance:
    """
    Handles target occlusion during Supercruise navigation.
    
    Uses compass-based closed-loop steering to find an escape heading away from
    the obstruction, then flies away for a guaranteed duration before retrying
    alignment.
    """

    def __init__(self, ap):
        """
        Initialize the SupercruiseAvoidance handler.
        
        Args:
            ap: The EDAutopilot instance for accessing ship controls and config.
        """
        self.ap = ap

    def _is_path_clear(self, scr_reg) -> bool:
        """
        Check if the current flight path is clear (no bright star ahead).
        """
        sun_percent = scr_reg.sun_percent(scr_reg.screen)
        if sun_percent > SUN_BRIGHTNESS_THRESHOLD:
            logger.warning(f'SupercruiseAvoidance: Star detected ahead ({sun_percent}% > {SUN_BRIGHTNESS_THRESHOLD}%)')
            return False
        return True

    def _acquire_escape_heading(self, scr_reg) -> tuple:
        """
        Stage A: Acquire escape heading using closed-loop compass steering.
        
        Pitches up until the compass shows the destination pip at the BOTTOM
        of the compass (y <= -edge_threshold) AND optionally behind (z < 0,
        hollow pip marker).
        
        This ensures we are truly facing away from the obstruction before
        beginning the fly-away phase.
        
        Returns:
            tuple: (success: bool, pitch_duration: float)
                - success: True if escape heading was acquired via compass gate
                - pitch_duration: Seconds spent pitching
        """
        require_behind = self.ap.config.get('SupercruiseAvoidanceRequireBehindPip', True)
        edge_threshold = self.ap.config.get('SupercruiseAvoidanceCompassEdgeThreshold', 0.9)
        timeout = self.ap.config.get('SupercruiseAvoidanceEscapeHeadingTimeoutSeconds', 12.0)
        min_pitch = self.ap.config.get('SupercruiseAvoidanceMinPitchSeconds', 1.5)
        
        logger.info(f"SupercruiseAvoidance: Acquiring escape heading "
                   f"(edge={edge_threshold}, behind={require_behind}, timeout={timeout}s, min={min_pitch}s)")
        
        start_time = time.time()
        self.ap.keys.send('PitchUpButton', state=1)  # Press and hold
        
        gate_satisfied = False
        last_nav_log = 0
        
        try:
            while (time.time() - start_time) < timeout:
                nav = self.ap.get_nav_offset(scr_reg)
                compass_conf = nav.get('compass_conf', 0.0)
                nav_conf = nav.get('nav_conf', 0.0)
                elapsed = time.time() - start_time
                
                # Log compass state periodically (every ~1s)
                if elapsed - last_nav_log >= 1.0:
                    logger.debug(f"Escape heading: y={nav['y']:.2f} z={nav['z']:.1f} "
                                f"conf={compass_conf:.2f}/{nav_conf:.2f} elapsed={elapsed:.1f}s")
                    last_nav_log = elapsed
                
                # Check compass reliability
                if compass_conf > COMPASS_CONFIDENCE_THRESHOLD and nav_conf > NAVPOINT_CONFIDENCE_THRESHOLD:
                    # Check if pip is at bottom of compass (y near -1.0)
                    y_ok = nav['y'] <= -edge_threshold
                    
                    # Check if pip is behind (hollow marker, z < 0) - optional
                    z_ok = (nav['z'] < 0) if require_behind else True
                    
                    # Only exit if we've also met minimum pitch time
                    if y_ok and z_ok and elapsed >= min_pitch:
                        logger.info(f"Escape heading acquired: y={nav['y']:.2f} z={nav['z']:.1f} "
                                   f"conf={compass_conf:.2f}/{nav_conf:.2f} (elapsed={elapsed:.1f}s)")
                        gate_satisfied = True
                        break
                
                time.sleep(0.1)
        finally:
            self.ap.keys.send('PitchUpButton', state=0)  # Release
        
        duration = time.time() - start_time
        
        if not gate_satisfied:
            logger.warning(f"Escape heading: compass gate timed out after {duration:.1f}s")
        
        return (gate_satisfied, duration)

    def _fallback_escape(self, scr_reg):
        """
        Fallback escape maneuver when compass is unreliable.
        
        Performs a deterministic "turn around and climb":
        - Yaw 180° to face opposite direction
        - Pitch up 45° for additional clearance
        """
        logger.info("SupercruiseAvoidance: Compass unreliable, using 180° yaw fallback")
        self.ap.ap_ckb('log', 'Compass unreliable, fallback escape')
        
        # Yaw 180 degrees to face away
        self.ap.yawRight(180)
        time.sleep(0.5)
        
        # Pitch up for additional clearance
        self.ap.pitchUp(45)

    def _pitch_away(self, scr_reg) -> float:
        """
        DEPRECATED: Legacy pitch method, kept for reference.
        Use _acquire_escape_heading() instead.
        """
        # This method is now replaced by _acquire_escape_heading()
        # but kept for backward compatibility if UseCompassGate is disabled
        use_gate = self.ap.config.get('SupercruiseAvoidanceUseCompassGate', False)
        pitch_rate = getattr(self.ap, 'pitchrate', 10.0)
        if pitch_rate <= 0:
            pitch_rate = 10.0

        if not use_gate:
            # Fixed 90 degree pitch (legacy behavior)
            logger.info("SupercruiseAvoidance: Pitching fixed 90 degrees (legacy)")
            self.ap.pitchUp(90)
            return 90.0 / pitch_rate
        else:
            # Use new escape heading acquisition
            success, duration = self._acquire_escape_heading(scr_reg)
            if not success:
                self._fallback_escape(scr_reg)
                return duration + 3.0  # Approximate additional time from fallback
            return duration

    def _attempt_maneuver(self, scr_reg, duration, yaw_drift_deg, attempt_idx, is_hard_escape=False) -> bool:
        """
        Perform a single escape maneuver attempt.
        
        Two-stage approach:
        1. Acquire escape heading (compass-based or fallback)
        2. Fly away for GUARANTEED duration (no early exit based on occlusion)
        """
        logger.info(f"SupercruiseAvoidance: Attempt {attempt_idx+1} (Hard={is_hard_escape}) "
                   f"- Duration {duration}s, Yaw {yaw_drift_deg}deg")
        self.ap.ap_ckb('log+vce', f"Avoidance attempt {attempt_idx+1}")

        # Phase 1: Slow Down
        self.ap.keys.send('SetSpeed50')
        time.sleep(2) 

        # Phase 2: Acquire Escape Heading (replaces simple pitch)
        success, pitch_duration = self._acquire_escape_heading(scr_reg)
        if not success:
            # Compass was unreliable - use fallback
            self._fallback_escape(scr_reg)
            pitch_duration = 3.0  # Approximate duration for fallback maneuver
        
        logger.debug(f"SupercruiseAvoidance: Escape heading phase complete ({pitch_duration:.2f}s)")
        
        # Phase 3: Yaw Drift (Optional, for retries to try different escape vector)
        if yaw_drift_deg > 0:
            logger.debug(f"SupercruiseAvoidance: Yawing {yaw_drift_deg} deg")
            self.ap.yawRight(yaw_drift_deg)

        # Phase 4: Fly Away - GUARANTEED DURATION
        # Important: Do NOT exit early based on is_destination_occluded()
        # The purpose is to create distance from the obstructing body
        logger.info(f"SupercruiseAvoidance: Flying away for {duration}s (guaranteed)")
        self.ap.keys.send('SetSpeed100')
        start_flight = time.time()
        
        maneuver_aborted = False

        while (time.time() - start_flight) < duration:
            # Safety check: Star ahead (we must avoid)
            if not self._is_path_clear(scr_reg):
                logger.warning('SupercruiseAvoidance: Star detected during fly-away! Pitching up to avoid.')
                self.ap.ap_ckb('log', 'Star detected, pitching up')
                
                # Pitch up for a short duration to clear the star
                self.ap.keys.send('PitchUpButton', state=1)
                time.sleep(2.5)
                self.ap.keys.send('PitchUpButton', state=0)
                
                # Do NOT abort - continue the fly-away to ensure we distance from the original occlusion
            
            # Safety check: Interdiction
            if self.ap.interdiction_check():
                logger.warning('SupercruiseAvoidance: Interdicted during fly-away')
                return True  # Interdiction handled, exit
            
            # NOTE: We do NOT check is_destination_occluded() here
            # The fly-away must complete to ensure we've moved into empty space
            
            time.sleep(1)

        # If aborted due to star, recovery routine
        if maneuver_aborted:
            # Immediately restore SC-safe throttle
            self.ap.keys.send('SetSpeed50')
            
            # Only run SunAvoidance if we're on an inter-system route
            if self.ap.is_inter_system_route_active():
                self.ap.sun_avoid(scr_reg)
            else:
                logger.debug('SupercruiseAvoidance: Skipping SunAvoidance (no inter-system route)')
            
            self.ap.nav_align(scr_reg)
            
            # Reassert SC-safe throttle
            self.ap.keys.send('SetSpeed50')
            return False

        # Phase 5: Pitch Back / Return
        logger.debug("SupercruiseAvoidance: Fly-away complete, pitching back")
        self.ap.keys.send('SetSpeed50')
        time.sleep(2)
        
        # Calculate degrees to pitch back down based on how long we pitched
        pitch_rate = getattr(self.ap, 'pitchrate', 10.0)
        if pitch_rate <= 0:
            pitch_rate = 10.0
        deg_to_pitch_down = pitch_duration * pitch_rate
        
        logger.debug(f"SupercruiseAvoidance: Pitching back down approx {deg_to_pitch_down:.1f} deg")
        self.ap.pitchDown(deg_to_pitch_down)
        
        # Reverse yaw drift
        if yaw_drift_deg > 0:
            self.ap.yawLeft(yaw_drift_deg)

        # Phase 6: Align and Check
        logger.debug("SupercruiseAvoidance: Re-aligning to target")
        self.ap.nav_align(scr_reg)
        
        # Check if occlusion is cleared (with brief debounce)
        occluded = self.ap.is_destination_occluded(scr_reg)
        if occluded:
            time.sleep(0.3)
            occluded = self.ap.is_destination_occluded(scr_reg)

        if occluded:
            logger.info("SupercruiseAvoidance: Destination still occluded after maneuver.")
            return False
        else:
            logger.info("SupercruiseAvoidance: Destination clear!")
            return True

    def execute(self, scr_reg) -> bool:
        """
        Execute the supercruise repositioning maneuver with retries.
        
        Uses compass-based escape heading acquisition to ensure we're facing
        away from the obstruction before flying away.
        
        Returns:
            bool: True if obstruction was cleared, False otherwise
        """
        # ============ SAFETY GUARD ============
        # If the solid destination circle is visible, abort avoidance (false trigger)
        dest_offset = self.ap.get_destination_offset(scr_reg)
        if dest_offset is not None:
            logger.info("SupercruiseAvoidance: Aborted - Target is visible (false trigger)")
            self.ap.ap_ckb('log', 'Avoidance aborted: Target visible')
            return True  # Treat as "cleared" to prevent retry loops
        
        max_attempts = self.ap.config.get('SupercruiseAvoidanceMaxAttempts', 3)
        base_duration = self.ap.config.get('SupercruiseAvoidanceDurationBase', 60)
        duration_max = self.ap.config.get('SupercruiseAvoidanceDurationMax', 120)
        yaw_increment = self.ap.config.get('SupercruiseAvoidanceYawDegrees', 15)
        hard_escape_seconds = self.ap.config.get('SupercruiseAvoidanceHardEscapeSeconds', 120)

        logger.info(f'SupercruiseAvoidance: Starting avoidance sequence (Max Attempts: {max_attempts})')
        self.ap.ap_ckb('log+vce', 'Target occluded, avoiding')

        for i in range(max_attempts):
            # Increase duration on retries
            duration = base_duration + (i * 30)
            duration = min(duration, duration_max)
            
            # Apply yaw drift only on retries to try different escape vectors
            yaw = 0 if i == 0 else yaw_increment
            
            success = self._attempt_maneuver(scr_reg, duration, yaw, i)
            if success:
                self.ap.ap_ckb('log+vce', 'Obstruction cleared')
                return True
        
        # All standard attempts failed - Hard Escape
        logger.warning("SupercruiseAvoidance: Standard attempts failed. Initiating HARD ESCAPE.")
        self.ap.ap_ckb('log+vce', 'Hard Escape Initiated')
        
        # Hard escape: Long duration, larger yaw drift
        self._attempt_maneuver(scr_reg, hard_escape_seconds, yaw_increment * 1.5, 99, is_hard_escape=True)
        
        self.ap.ap_ckb('log+vce', 'Avoidance Sequence Complete')
        return True
