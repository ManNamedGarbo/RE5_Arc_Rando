import json, os, subprocess, shutil, logging, time, concurrent.futures, threading, sys, xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog

# Set up logging
try:
    if getattr(sys, 'frozen', False):
        exe_folder = os.path.dirname(sys.executable)  # For PyInstaller executable
    else:
        exe_folder = os.path.dirname(os.path.abspath(__file__))  # For running as a script
    os.chdir(exe_folder)  # Set the working directory to the folder containing the executable
    logs_folder = os.path.join(exe_folder, 'logs')
    os.makedirs(logs_folder, exist_ok=True)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(logs_folder, f'process_log_{timestamp}.log')
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
except Exception as e:
    print(f"Failed to initialize logging: {e}")

def select_folder():
    print("Please navigate to your Resident Evil 5 installation and select the Archive folder.")
    print(r"This is present by default at '.\Resident Evil 5\nativePC_MT\Image\Archive'.")
    root = tk.Tk()
    root.withdraw()
    folder_selected = filedialog.askdirectory(title="Select the Archive Folder")
    return folder_selected

def find_input_json(exe_folder):
    for filename in os.listdir(exe_folder):
        if filename.startswith('AP') and filename.endswith('.json'):
            return os.path.join(exe_folder, filename)
    raise FileNotFoundError("No AP JSON file found in the executable directory.")

def unpack_arc_file(arc_file, arc_folder):
    original_arc_path = os.path.join(arc_folder, arc_file)
    temp_arc_path = os.path.join(exe_folder, arc_file)
    logging.info(f"Copying {arc_file} from {arc_folder} to {exe_folder}...")
    shutil.copy2(original_arc_path, temp_arc_path)
    logging.info(f"Successfully copied {arc_file}.")
    logging.info(f"Unpacking {arc_file} using pc-re5.bat...")
    script_name = 'pc-re5.bat' if os.name == 'nt' else 'pc-re5.sh'
    subprocess.run([os.path.join(exe_folder, script_name), temp_arc_path], check=True)
    logging.info(f"Successfully unpacked {arc_file}.")

def process_arc_file_batch(output_folder, arc_file, modifications):
    unpack_folder = os.path.splitext(arc_file)[0]
    xml_file_path = os.path.join(exe_folder, unpack_folder, 'stage', unpack_folder, 'soft', f'{unpack_folder}_item.lot.xml')

    if not os.path.exists(xml_file_path):
        logging.error(f"XML file {xml_file_path} not found. Skipping...")
        return

    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        # Process each modification
        for new_item_id, vanilla_item, xcord, ycord, zcord in modifications:
            # Convert coordinates to floats for more accurate comparison
            target_x = float(xcord)
            target_y = float(ycord)
            target_z = float(zcord)
            
            # First, find and log all elements with matching mUnitClass
            all_matches = []
            special_matches = []  # For (0,0,0) with ItemType 2 or 3
            logging.info(f"Searching for all instances of {vanilla_item} in {xml_file_path}")
            logging.info(f"Target coordinates: ({target_x}, {target_y}, {target_z})")
            
            # Format as a table header
            logging.info(f"{'Match #':<8}{'X':<20}{'Y':<20}{'Z':<20}{'Distance':<15}{'ItemType':<10}")
            logging.info("-" * 90)
            
            # Find all elements with matching mUnitClass
            match_count = 0
            for elem in root.findall(".//classref[@type='1637199632']"):
                unit_class = elem.find("./string[@name='mUnitClass']")
                if unit_class is not None and unit_class.get("value") == vanilla_item:
                    mp_info = elem.find("./classref[@name='mpInfo']")
                    if mp_info is not None:
                        position = mp_info.find("./vector3[@name='mPosition']")
                        
                        # Check for ItemType
                        item_type = None
                        item_set = mp_info.find(".//class[@name='mItemSet']")
                        if item_set is not None:
                            item_type_elem = item_set.find("./u8[@name='ItemType']")
                            if item_type_elem is not None:
                                item_type = int(item_type_elem.get("value", "0"))
                        
                        if position is not None:
                            try:
                                x = float(position.get('x', '0'))
                                y = float(position.get('y', '0'))
                                z = float(position.get('z', '0'))
                                
                                # Calculate distance
                                distance = ((x - target_x) ** 2 + (y - target_y) ** 2 + (z - target_z) ** 2) ** 0.5
                                
                                match_count += 1
                                # Log as table row
                                logging.info(f"{match_count:<8}{x:<20}{y:<20}{z:<20}{distance:<15.2f}{item_type if item_type is not None else 'N/A':<10}")
                                
                                # Check for special case: (0,0,0) coordinates with ItemType 2 or 3
                                if x == 0 and y == 0 and z == 0 and item_type in (2, 3):
                                    logging.info(f"Found special case: coordinates (0,0,0) with ItemType {item_type}")
                                    special_matches.append({
                                        'distance': 0,  # Priority match
                                        'coordinates': (x, y, z),
                                        'element': elem,
                                        'item_type': item_type
                                    })
                                else:
                                    # Store the match with its distance and coordinates
                                    all_matches.append({
                                        'distance': distance,
                                        'coordinates': (x, y, z),
                                        'element': elem,
                                        'item_type': item_type
                                    })
                            except ValueError:
                                logging.error(f"Invalid coordinate format in {xml_file_path}")
            
            logging.info("-" * 90)  # End of table
            
            # Log summary of found coordinates
            if all_matches or special_matches:
                logging.info(f"Found {len(all_matches)} regular matches and {len(special_matches)} special matches for {vanilla_item} in {xml_file_path}")
            else:
                logging.error(f"No matching coordinates found for {vanilla_item} in {xml_file_path}.")
                continue  # Skip to next modification if no matches found
            
            # Determine which match to use
            best_match = None
            
            # If we have special matches (0,0,0 with ItemType 2 or 3), use the first one
            if special_matches:
                best_match = special_matches[0]
                logging.info(f"Using special match for {vanilla_item}: coords (0,0,0), ItemType {best_match['item_type']}")
            # Otherwise sort regular matches by distance and get the closest one
            elif all_matches:
                all_matches.sort(key=lambda x: x['distance'])
                best_match = all_matches[0]
                logging.info(f"Using closest match for {vanilla_item}: coords {best_match['coordinates']}, distance {best_match['distance']:.2f}")
            
            if best_match:
                # Update the ItemId
                mp_info = best_match['element'].find("./classref[@name='mpInfo']")
                item_set = mp_info.find(".//class[@name='mItemSet']") if mp_info is not None else None
                
                if item_set is not None:
                    item_id_elem = item_set.find("./u16[@name='ItemId']")
                    if item_id_elem is not None:
                        old_value = item_id_elem.get("value")
                        item_id_elem.set("value", str(new_item_id))
                        if 'item_type' in best_match and best_match['item_type'] in (2, 3):
                            logging.info(f"Updated ItemId from {old_value} to {new_item_id} for {vanilla_item} at (0,0,0) with ItemType {best_match['item_type']} in {xml_file_path}.")
                        else:
                            logging.info(f"Updated ItemId from {old_value} to {new_item_id} for {vanilla_item} at {best_match['coordinates']} in {xml_file_path}.")
                    else:
                        logging.error(f"ItemId element not found for {vanilla_item} at {best_match['coordinates']} in {xml_file_path}.")
                else:
                    logging.error(f"mItemSet not found for {vanilla_item} at {best_match['coordinates']} in {xml_file_path}.")
            else:
                logging.error(f"No valid matches found for {vanilla_item} in {xml_file_path} after checking both regular and special cases.")
        
        # Save the modified XML
        tree.write(xml_file_path)
        logging.info(f"Saved changes to {xml_file_path}")
        
        # Repack the arc file
        repack_arc_file(arc_file)
        
    except Exception as e:
        logging.error(f"Error processing {xml_file_path}: {e}")
        logging.exception("Stack trace:")  # This will log the full stack trace

def repack_arc_file(arc_file):
    try:
        # Assume there's a repacking script similar to the unpacking one
        script_name = 'pc-re5-pack.bat' if os.name == 'nt' else 'pc-re5-pack.sh'
        unpack_folder = os.path.splitext(arc_file)[0]
        
        logging.info(f"Repacking {unpack_folder} to {arc_file}...")
        subprocess.run([os.path.join(exe_folder, script_name), os.path.join(exe_folder, unpack_folder)], check=True)
        logging.info(f"Successfully repacked {arc_file}.")
    except Exception as e:
        logging.error(f"Error repacking {arc_file}: {e}")

def update_item_ids(arc_folder):
    try:
        input_file = find_input_json(exe_folder)
        input_filename = os.path.splitext(os.path.basename(input_file))[0]
        output_folder = os.path.join(exe_folder, input_filename + '_output')
        os.makedirs(output_folder, exist_ok=True)

        with open(input_file, 'r') as f:
            input_data = json.load(f)
        logging.info(f"Loaded {len(input_data)} entries from {input_file}.")

        # Group modifications by arc_file
        modifications_by_file = {}
        for entry in input_data:
            # Extract the necessary fields
            new_item_id = entry.get('item_xml_id')
            vanilla_item = entry.get('vanilla_item')
            arc_file = entry.get('arc_file')
            xcord = entry.get('xcord')
            ycord = entry.get('ycord')
            zcord = entry.get('zcord')
            
            if None in (new_item_id, vanilla_item, arc_file, xcord, ycord, zcord):
                logging.error(f"Missing required fields in entry: {entry}")
                continue
                
            # Add to modifications dictionary grouped by arc_file
            modifications_by_file.setdefault(arc_file, []).append(
                (new_item_id, vanilla_item, xcord, ycord, zcord)
            )

        # Process each arc file
        for arc_file in modifications_by_file.keys():
            logging.info(f"Processing {arc_file}...")
            unpack_arc_file(arc_file, arc_folder)
            process_arc_file_batch(output_folder, arc_file, modifications_by_file[arc_file])

        logging.info("Batch processing completed successfully.")

        # Cleanup code
        logging.info("Cleaning up leftover unpacked folders...")
        for folder in os.listdir(exe_folder):
            folder_path = os.path.join(exe_folder, folder)
            if os.path.isdir(folder_path) and folder.startswith('s') and folder[1:].isdigit():
                logging.info(f"Removing unpacked folder {folder_path}...")
                shutil.rmtree(folder_path, ignore_errors=True)
        logging.info("Executable folder cleanup completed.")

    except Exception as e:
        logging.error(f"Error during the update process: {e}")
        print(f"Error: {e}")
        
        # Attempt cleanup even after error
        try:
            logging.info("Cleaning up after error...")
            for folder in os.listdir(exe_folder):
                folder_path = os.path.join(exe_folder, folder)
                if os.path.isdir(folder_path) and folder.startswith('s') and folder[1:].isdigit():
                    logging.info(f"Removing unpacked folder {folder_path}...")
                    shutil.rmtree(folder_path, ignore_errors=True)
            logging.info("Error cleanup completed.")
        except Exception as cleanup_error:
            logging.error(f"Error during cleanup: {cleanup_error}")

if __name__ == "__main__":
    arc_folder = select_folder()

    if not arc_folder:
        print("No folder selected. Exiting.")
    else:
        start_time = time.time()
        update_item_ids(arc_folder)
        duration = time.time() - start_time
        logging.info(f"Program completed in {duration:.2f} seconds.")
        print(f"Program completed in {duration:.2f} seconds.")