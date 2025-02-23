import json, os, subprocess, shutil, logging, time, concurrent.futures, threading
import tkinter as tk
from tkinter import filedialog

# Set up logging
try:
    if getattr(sys, 'frozen', False):
        exe_folder = os.path.dirname(sys.executable)  # Path for PyInstaller-bundled executable
    else:
        exe_folder = os.path.dirname(os.path.abspath(__file__))  # Path for running as a script
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
    subprocess.run([os.path.join(exe_folder, 'pc-re5.bat'), temp_arc_path], check=True)
    logging.info(f"Successfully unpacked {arc_file}.")

def process_arc_file_batch(output_folder, arc_file, modifications):
    unpack_folder = os.path.splitext(arc_file)[0]
    xml_file_path = os.path.join(exe_folder, unpack_folder, 'stage', unpack_folder, 'soft', f'{unpack_folder}_item.lot.xml')

    if not os.path.exists(xml_file_path):
        logging.error(f"XML file {xml_file_path} not found. Skipping...")
        return

    try:
        with open(xml_file_path, 'r') as file:
            lines = file.readlines()
        
        for line_number, new_item_id in modifications:
            if line_number - 1 < len(lines):
                if '<u16 name="ItemId" value="' in lines[line_number - 1]:
                    start = lines[line_number - 1].find('<u16 name="ItemId" value="') + len('<u16 name="ItemId" value="')
                    end = lines[line_number - 1].find('"', start)
                    lines[line_number - 1] = (
                        lines[line_number - 1][:start] + str(new_item_id) + lines[line_number - 1][end:]
                    )
                else:
                    logging.error(f"ItemId not found at line {line_number} in {xml_file_path}. Skipping...")
            else:
                logging.error(f"Line number {line_number} out of range in {xml_file_path}. Skipping...")
        
        with open(xml_file_path, 'w') as file:
            file.writelines(lines)
        
        logging.info(f"Applied all changes to {xml_file_path}.")
        subprocess.run([os.path.join(exe_folder, 'pc-re5.bat'), os.path.join(exe_folder, unpack_folder)], check=True)

        repacked_file = os.path.join(exe_folder, f"{unpack_folder}.arc")
        logging.info(f"Moving repacked {unpack_folder}.arc to output folder...")
        shutil.move(repacked_file, os.path.join(output_folder, f"{unpack_folder}.arc"))
        logging.info(f"Successfully moved {unpack_folder}.arc to output.")
        shutil.rmtree(os.path.join(exe_folder, unpack_folder))

    except Exception as e:
        logging.error(f"Error processing {xml_file_path}: {e}")

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