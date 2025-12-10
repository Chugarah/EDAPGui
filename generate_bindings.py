import xml.etree.ElementTree as ET
import os
import shutil

# Helper to define key with optional modifier
def bind(key, modifier=None):
    return {"Key": key, "Modifier": modifier}

# Optimized Binding Set (Numpad + Modifiers)
BINDINGS_OPTIMIZED = {
    # --- UI Navigation (Alt + Numpad) ---
    "UI_Up": bind("Key_Numpad_8", "Key_LeftAlt"),
    "UI_Down": bind("Key_Numpad_2", "Key_LeftAlt"),
    "UI_Left": bind("Key_Numpad_4", "Key_LeftAlt"),
    "UI_Right": bind("Key_Numpad_6", "Key_LeftAlt"),
    "UI_Select": bind("Key_Numpad_Enter", "Key_LeftAlt"),
    "UI_Back": bind("Key_Numpad_Decimal", "Key_LeftAlt"),
    "CycleNextPanel": bind("Key_Numpad_9", "Key_LeftAlt"),
    "CyclePreviousPanel": bind("Key_Numpad_7", "Key_LeftAlt"),

    # --- Flight Controls (Numpad Direct) ---
    "SetSpeedZero": bind("Key_Numpad_0"),
    "SetSpeed50": bind("Key_Numpad_5"),
    "SetSpeed100": bind("Key_Numpad_1"),
    "SetSpeed75": bind("Key_Numpad_3"),
    
    "YawLeftButton": bind("Key_Numpad_4"),
    "YawRightButton": bind("Key_Numpad_6"),
    "PitchUpButton": bind("Key_Numpad_2"),   # Down direction = Pitch Up
    "PitchDownButton": bind("Key_Numpad_8"), # Up direction = Pitch Down
    "RollLeftButton": bind("Key_Numpad_7"),
    "RollRightButton": bind("Key_Numpad_9"),

    # --- Actions (Ctrl + Numpad) ---
    "SelectTarget": bind("Key_Numpad_Decimal", "Key_LeftControl"),
    "HyperSuperCombination": bind("Key_Numpad_Enter", "Key_LeftControl"),
    "Supercruise": bind("Key_Numpad_Divide", "Key_LeftControl"),
    "DeployHardpointToggle": bind("Key_Numpad_Multiply", "Key_LeftControl"),
    "LandingGearToggle": bind("Key_Numpad_Subtract", "Key_LeftControl"),
    "DeployHeatSink": bind("Key_Numpad_Add", "Key_LeftControl"),

    # --- Missing Keys (Mapped to avoid warnings) ---
    "GalaxyMapOpen": bind("Key_M", "Key_LeftControl"),
    "SystemMapOpen": bind("Key_Comma", "Key_LeftControl"),
    "TargetNextRouteSystem": bind("Key_Numpad_0", "Key_LeftControl"),
    "HeadLookReset": bind("Key_Numpad_5", "Key_LeftControl"),
    "PrimaryFire": bind("Key_Numpad_1", "Key_LeftControl"),
    "SecondaryFire": bind("Key_Numpad_2", "Key_LeftControl"),
    "MouseReset": bind("Key_Numpad_3", "Key_LeftControl"),
    
    # --- Fix FSS Conflict ---
    # Assigning distinct keys to these to resolve the 'Key_Apostrophe' collision warning
    "ExplorationFSSEnter": bind("Key_Apostrophe", "Key_LeftAlt"), 
    "ExplorationFSSQuit": bind("Key_Apostrophe", "Key_LeftControl"),
}

# Keys that EDAP uses for global hotkeys. We must remove these from ANY game binding to prevent conflicts.
EDAP_HOTKEYS = ["Key_Home", "Key_End", "Key_Insert", "Key_PageUp"]

SOURCE_FILE = os.path.join("configs", "Bindings", "Custom.4.2.binds")
OUTPUT_DIR = os.path.join("configs", "Bindings")

def clear_conflicting_keys(root):
    """
    Scans all bindings. If a Primary or Secondary binding uses a key in EDAP_HOTKEYS,
    it clears that binding (sets it to NoDevice).
    """
    print("Scanning for conflicts with EDAP Hotkeys (Home, End, Insert, PageUp)...")
    cleared_count = 0
    for command in root:
        for device_slot in ["Primary", "Secondary"]:
            slot = command.find(device_slot)
            if slot is not None:
                key = slot.get("Key")
                if key in EDAP_HOTKEYS:
                    print(f"  Conflict found: {command.tag} [{device_slot}] uses {key}. Clearing...")
                    slot.set("Device", "{NoDevice}")
                    slot.set("Key", "")
                    # Remove modifier if present
                    mod = slot.find("Modifier")
                    if mod is not None:
                        slot.remove(mod)
                    cleared_count += 1
    print(f"Cleared {cleared_count} conflicting bindings.")

def generate_binding_file(preset_name, bindings_map, output_filename):
    if not os.path.exists(SOURCE_FILE):
        print(f"Error: Source file {SOURCE_FILE} not found.")
        return

    tree = ET.parse(SOURCE_FILE)
    root = tree.getroot()

    # Update Root attributes
    root.set("PresetName", preset_name)
    root.set("MajorVersion", "4")
    root.set("MinorVersion", "0")

    # Step 1: Clear conflicts
    clear_conflicting_keys(root)

    print(f"Generating {preset_name}...")

    for command, binding_def in bindings_map.items():
        # Handle simple string format from old maps if necessary (backward compatibility)
        if isinstance(binding_def, str):
            binding_def = {"Key": binding_def, "Modifier": None}
            
        key = binding_def["Key"]
        modifier = binding_def["Modifier"]

        # Find the command element
        element = root.find(command)
        if element is None:
            print(f"  Warning: Command '{command}' not found in source. Creating it.")
            element = ET.SubElement(root, command)
            ET.SubElement(element, "Primary", Device="{NoDevice}", Key="")
            ET.SubElement(element, "Secondary", Device="{NoDevice}", Key="")
        
        # Update Secondary binding
        secondary = element.find("Secondary")
        if secondary is None:
            secondary = ET.SubElement(element, "Secondary")
        
        secondary.set("Device", "Keyboard")
        secondary.set("Key", key)
        
        # Handle Modifier
        # Remove existing modifier if any
        existing_mod = secondary.find("Modifier")
        if existing_mod is not None:
            secondary.remove(existing_mod)
            
        if modifier:
            ET.SubElement(secondary, "Modifier", Device="Keyboard", Key=modifier)
            print(f"  Set {command} Secondary to {modifier} + {key}")
        else:
            print(f"  Set {command} Secondary to {key}")

    output_path = os.path.join(OUTPUT_DIR, output_filename)
    tree.write(output_path, encoding="UTF-8", xml_declaration=True)
    print(f"Saved to {output_path}")

def main():
    print("Generating EDAPGui Binding Templates...")
    
    # Generate Optimized Version
    generate_binding_file("EDAP_Optimized", BINDINGS_OPTIMIZED, "EDAP_Optimized.4.0.binds")

    print("\nDone. Copy the generated .binds files to your Elite Dangerous bindings folder:")
    print("%LOCALAPPDATA%\\Frontier Developments\\Elite Dangerous\\Options\\Bindings")

if __name__ == "__main__":
    main()
