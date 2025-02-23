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
        
        for line_number, new_item_id, vanilla_item in modifications:
            found = False
            closest_unit_class = None
            
            # Find the closest mUnitClass with matching vanilla_item
            closest_distance = float('inf')
            for elem in root.iter('mUnitClass'):
                if vanilla_item in elem.attrib.get('name', ''):
                    current_line = list(root.iter()).index(elem)
                    distance = abs(current_line - (line_number - 1))
                    if distance < closest_distance:
                        closest_distance = distance
                        closest_unit_class = elem
            
            if closest_unit_class is not None:
                # Update the corresponding ClassRef's ItemId below the found mUnitClass
                for class_ref in closest_unit_class.iter('ClassRef'):
                    item_id_elem = class_ref.find(".//u16[@name='ItemId']")
                    if item_id_elem is not None:
                        old_value = item_id_elem.attrib.get('value')
                        item_id_elem.set('value', str(new_item_id))
                        logging.info(f"Updated ItemId from {old_value} to {new_item_id} for {vanilla_item} in {xml_file_path}.")
                        found = True
                        break
            
            if not found:
                logging.error(f"Vanilla item '{vanilla_item}' not found in {xml_file_path}. Attempting to find nearest ItemId based on line number {line_number}.")
                closest_distance = float('inf')
                closest_item_id_elem = None
                for i, elem in enumerate(root.iter('u16')):
                    if elem.attrib.get('name') == 'ItemId':
                        distance = abs(i - (line_number - 1))
                        if distance < closest_distance:
                            closest_distance = distance
                            closest_item_id_elem = elem
                if closest_item_id_elem is not None:
                    old_value = closest_item_id_elem.attrib.get('value')
                    closest_item_id_elem.set('value', str(new_item_id))
                    logging.info(f"Updated nearest ItemId from {old_value} to {new_item_id} in {xml_file_path}.")
                    found = True
                else:
                    logging.error(f"No nearby ItemId found around line {line_number} in {xml_file_path}. Skipping...")

def update_item_ids(arc_folder):
    try:
        input_file = find_input_json(exe_folder)
        input_filename = os.path.splitext(os.path.basename(input_file))[0]
        output_folder = os.path.join(exe_folder, input_filename + '_output')
        os.makedirs(output_folder, exist_ok=True)

        with open(input_file, 'r') as f:
            input_data = json.load(f)
        logging.info(f"Loaded {len(input_data)} entries from {input_file}.")

        modifications_by_file = {}
        for entry in input_data:
            location_id = entry['location_unique_id']
            new_item_id = entry['item_xml_id']
            parts = list(map(int, location_id.split('_')))
            if len(parts) >= 2:
                arc_number, line_number = parts[0], parts[1]
                arc_file = f"s{arc_number}.arc"
                modifications_by_file.setdefault(arc_file, []).append((line_number, new_item_id))
            else:
                logging.error(f"Invalid location_unique_id format: {location_id}. Skipping...")

        for arc_file in modifications_by_file.keys():
            logging.info(f"Unpacking {arc_file}...")
            unpack_arc_file(arc_file, arc_folder)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_arc_file_batch, output_folder, arc_file, modifications)
                       for arc_file, modifications in modifications_by_file.items()]
            concurrent.futures.wait(futures)

        logging.info("Batch processing completed successfully.")

    except Exception as e:
        logging.error(f"Error during the update process: {e}")
        print(f"Error: {e}")

    logging.info("Cleaning up leftover unpacked folders...")
    for folder in os.listdir(exe_folder):
        folder_path = os.path.join(exe_folder, folder)
        if os.path.isdir(folder_path) and folder.startswith('s') and folder[1:].isdigit():
            logging.info(f"Removing unpacked folder {folder_path}...")
            shutil.rmtree(folder_path)
    logging.info("Executable folder cleanup completed.")

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
