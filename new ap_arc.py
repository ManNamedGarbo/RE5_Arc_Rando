import json, os, subprocess, shutil, logging, time, concurrent.futures, threading, sys, xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog
from typing import Dict, List, Tuple

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

class XMLItemCache:
    def __init__(self, xml_file_path: str):
        """
        Initialize the cache by parsing the XML file and storing item information
        
        :param xml_file_path: Path to the XML file to parse
        """
        self.xml_file_path = xml_file_path
        self.cache: Dict[str, List[Dict]] = {}
        self._parse_xml()

    def _parse_xml(self):
        """
        Parse the XML file and build a comprehensive cache of item information
        """
        try:
            tree = ET.parse(self.xml_file_path)
            root = tree.getroot()
            
            # Iterate through all classref elements of the specific type
            for elem in root.findall(".//classref[@type='1637199632']"):
                unit_class_elem = elem.find("./string[@name='mUnitClass']")
                if unit_class_elem is None:
                    continue
                
                unit_class = unit_class_elem.get("value")
                if not unit_class:
                    continue
                
                # Initialize list for this unit class if not exists
                if unit_class not in self.cache:
                    self.cache[unit_class] = []
                
                # Extract detailed information
                mp_info = elem.find("./classref[@name='mpInfo']")
                if mp_info is None:
                    continue
                
                # Position information
                position = mp_info.find("./vector3[@name='mPosition']")
                if position is None:
                    continue
                
                try:
                    x = float(position.get('x', '0'))
                    y = float(position.get('y', '0'))
                    z = float(position.get('z', '0'))
                except ValueError:
                    continue
                
                # Item set information
                item_type = None
                set_type = None
                item_id = None
                item_set = mp_info.find(".//class[@name='mItemSet']")
                if item_set is not None:
                    item_type_elem = item_set.find("./u8[@name='ItemType']")
                    set_type_elem = item_set.find("./u8[@name='SetType']")
                    item_id_elem = item_set.find("./u16[@name='ItemId']")
                    
                    item_type = int(item_type_elem.get("value", "0")) if item_type_elem is not None else None
                    set_type = int(set_type_elem.get("value", "0")) if set_type_elem is not None else None
                    item_id = int(item_id_elem.get("value", "0")) if item_id_elem is not None else None
                
                # Store comprehensive item information
                item_info = {
                    'element': elem,  # Keep the original XML element for modification
                    'coordinates': (x, y, z),
                    'item_type': item_type,
                    'set_type': set_type,
                    'item_id': item_id,
                    'distance': None  # Will be calculated during matching
                }
                
                self.cache[unit_class].append(item_info)
            
            logging.info(f"Cached {sum(len(items) for items in self.cache.values())} items from {self.xml_file_path}")
        
        except Exception as e:
            logging.error(f"Error parsing XML file {self.xml_file_path}: {e}")
            logging.exception("Stack trace:")

    def find_best_match(self, vanilla_item: str, target_x: float, target_y: float, target_z: float) -> Dict:
        """
        Find the best matching item based on unit class and coordinates
        
        :param vanilla_item: The unit class to match
        :param target_x: Target X coordinate
        :param target_y: Target Y coordinate
        :param target_z: Target Z coordinate
        :return: Best matching item information
        """
        # Check if the unit class exists in cache
        if vanilla_item not in self.cache or not self.cache[vanilla_item]:
            logging.error(f"No items found for unit class {vanilla_item}")
            return None
        
        # For SetType non-zero, look for (0,0,0) coordinates
        non_zero_set_type_matches = [
            item for item in self.cache[vanilla_item] 
            if item['set_type'] is not None and item['set_type'] != 0 
            and item['coordinates'] == (0, 0, 0)
        ]
        
        if non_zero_set_type_matches:
            logging.info(f"Found {len(non_zero_set_type_matches)} matches for {vanilla_item} with non-zero SetType")
            return non_zero_set_type_matches[0]
        
        # For SetType 0, find closest coordinates
        for item in self.cache[vanilla_item]:
            if item['set_type'] == 0:
                x, y, z = item['coordinates']
                # Calculate distance
                distance = ((x - target_x) ** 2 + (y - target_y) ** 2 + (z - target_z) ** 2) ** 0.5
                item['distance'] = distance
        
        # Filter SetType 0 items and sort by distance
        zero_set_type_matches = [
            item for item in self.cache[vanilla_item] 
            if item['set_type'] == 0 and item['distance'] is not None
        ]
        
        if zero_set_type_matches:
            best_match = min(zero_set_type_matches, key=lambda x: x['distance'])
            logging.info(f"Found closest match for {vanilla_item} at {best_match['coordinates']} with distance {best_match['distance']:.2f}")
            return best_match
        
        logging.error(f"No valid matches found for {vanilla_item}")
        return None

    def save_modifications(self, tree):
        """
        Save modifications to the XML file
        
        :param tree: Modified XML ElementTree
        """
        try:
            tree.write(self.xml_file_path)
            logging.info(f"Saved changes to {self.xml_file_path}")
        except Exception as e:
            logging.error(f"Error saving modifications to {self.xml_file_path}: {e}")

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
        # Create XML cache
        xml_cache = XMLItemCache(xml_file_path)
        
        # Parse the XML tree for modification
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        # Process each modification
        for new_item_id, vanilla_item, xcord, ycord, zcord in modifications:
            # Convert coordinates to floats for more accurate comparison
            target_x = float(xcord)
            target_y = float(ycord)
            target_z = float(zcord)
            
            # Find best match using the cache
            best_match = xml_cache.find_best_match(vanilla_item, target_x, target_y, target_z)
            
            if best_match is None:
                logging.error(f"No match found for {vanilla_item} with coordinates ({target_x}, {target_y}, {target_z})")
                continue
            
            # Update the ItemId
            mp_info = best_match['element'].find("./classref[@name='mpInfo']")
            item_set = mp_info.find(".//class[@name='mItemSet']") if mp_info is not None else None
            
            if item_set is not None:
                item_id_elem = item_set.find("./u16[@name='ItemId']")
                if item_id_elem is not None:
                    old_value = item_id_elem.get("value")
                    item_id_elem.set("value", str(new_item_id))
                    logging.info(f"Updated ItemId from {old_value} to {new_item_id} for {vanilla_item} at {best_match['coordinates']} with SetType {best_match.get('set_type', 'N/A')} in {xml_file_path}.")
                else:
                    logging.error(f"ItemId element not found for {vanilla_item} at {best_match['coordinates']} in {xml_file_path}.")
            else:
                logging.error(f"mItemSet not found for {vanilla_item} at {best_match['coordinates']} in {xml_file_path}.")
        
        # Save modifications using the cache method
        xml_cache.save_modifications(tree)
        
        # Repack the arc file
        repack_arc_file(arc_file)
        
    except Exception as e:
        logging.error(f"Error processing {xml_file_path}: {e}")
        logging.exception("Stack trace:")

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
                    shutil.rmtree
                    
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
