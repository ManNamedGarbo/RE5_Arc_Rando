import json
import os
import subprocess
import xml.etree.ElementTree as ET
import shutil
import logging
import time

# Set up logging
logging.basicConfig(filename='process_log.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_step_time(start_time, step_name):
    """Helper function to log the time taken for each step."""
    end_time = time.time()
    duration = end_time - start_time
    logging.info(f"{step_name} took {duration:.2f} seconds.")
    return end_time  # Return the new end_time for next step's timing

def load_location_mapping(mapping_file):
    """Load the location-to-file mapping from a JSON file."""
    try:
        print(f"Loading location mapping from {mapping_file}...")  # Print to show it's starting
        if not os.path.exists(mapping_file):
            raise FileNotFoundError(f"Mapping file {mapping_file} not found.")
        
        with open(mapping_file, 'r') as file:
            loaded_file = json.load(file)
            print("Loaded mapping file successfully.")  # Lets us know it loaded the file
            
            return loaded_file  # Return the loaded data
    except Exception as e:
        logging.error(f"Error loading mapping file {mapping_file}: {e}")
        print(f"Error loading mapping file {mapping_file}: {e}")  # Print the error, instead of only logging it.
        raise

def update_item_ids(input_file, arc_folder, mapping_file):
    start_time = time.time()  # Start measuring time for the entire process

    # Step 1: Load location-to-file mapping from the external JSON file
    logging.info("Starting to load location mappings...")
    step_start_time = time.time()
    try:
        location_to_file_mapping = load_location_mapping(mapping_file)
    except Exception as e:
        logging.error(f"Failed to load location mappings: {e}")
        return
    step_start_time = log_step_time(step_start_time, "Loading location mappings")

    # Step 2: Read the input JSON file (which contains locations and new ItemIDs)
    logging.info("Starting to read input JSON...")
    step_start_time = time.time()
    try:
        with open(input_file, 'r') as infile:
            input_data = json.load(infile)
    except Exception as e:
        logging.error(f"Error reading input file {input_file}: {e}")
        return
    step_start_time = log_step_time(step_start_time, "Reading input JSON")

    # List to keep track of the unpacked directories that need to be repacked
    unpacked_folders_to_repack = []

    # Step 3: Loop through input data (locations and ItemIDs)
    for i in range(0, len(input_data) - 1, 2):
        location_line = input_data[i]  # Location (e.g., "loc:uWp13")
        new_item_id = input_data[i + 1]  # New ItemID (e.g., 1025)

        # Extract location ID from the line (assumes format "loc:<location_id>")
        location_id = location_line.split(":")[1].strip()

        # Step 4: Determine which file corresponds to this location ID
        if location_id not in location_to_file_mapping:
            logging.warning(f"No output file mapped for location {location_id}. Skipping...")
            continue  # Skip if there's no file mapped for this location
        
        arc_file = location_to_file_mapping[location_id]
        arc_path = os.path.join(arc_folder, arc_file)  # Full path to the .arc file

        # Check if the .arc file exists
        if not os.path.exists(arc_path):
            logging.error(f"The file {arc_file} does not exist in the specified folder. Skipping...")
            continue

        # Step 5: Decrypt the .arc file using pc-re5.bat if not already unpacked
        unpack_folder = os.path.join(arc_folder, arc_file[:-4])  # Folder will be named like "s118"
        if os.path.exists(unpack_folder):
            logging.info(f"Folder {unpack_folder} already exists. Using unpacked files.")
        else:
            logging.info(f"Unpacking {arc_file}...")
            step_start_time = time.time()
            try:
                subprocess.run([os.path.join(arc_folder, 'pc-re5.bat'), arc_path], check=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"Error unpacking {arc_file}: {e}")
                continue
            step_start_time = log_step_time(step_start_time, f"Unpacking {arc_file}")

        # Step 6: Locate the XML file inside the unpacked folder
        xml_file_path = os.path.join(unpack_folder, "stage", arc_file[:-4], "soft", f"{arc_file[:-4]}_item.lot.xml")

        # Check if the XML file exists
        if not os.path.exists(xml_file_path):
            logging.error(f"The XML file {xml_file_path} does not exist. Skipping...")
            continue

        # Step 7: Parse the XML file
        logging.info(f"Starting to parse XML file {xml_file_path}...")
        step_start_time = time.time()
        try:
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
        except Exception as e:
            logging.error(f"Error parsing XML file {xml_file_path}: {e}")
            continue
        step_start_time = log_step_time(step_start_time, f"Parsing XML file {xml_file_path}")

        # Step 8: Search for the <classref> element with the location_id
        location_found = False
        for classref in root.findall(".//classref"):
            # Look for the location_id in the value attribute
            if classref.get("value") == location_id:
                location_found = True

                # Step 9: Find the <u16 name="ItemId" value="..."> and update the ItemID
                item_id_element = classref.find(".//u16[@name='ItemId']")
                if item_id_element is not None:
                    item_id_element.set("value", str(new_item_id))
                else:
                    logging.warning(f"<u16 name='ItemId'> not found in classref for location {location_id}.")
                    continue

                break  # Stop once the location is found and updated

        if not location_found:
            logging.warning(f"Location {location_id} not found in {xml_file_path}. Skipping...")
            continue

        # Step 10: Save the updated XML file
        logging.info(f"Saving updated XML file {xml_file_path}...")
        step_start_time = time.time()
        try:
            tree.write(xml_file_path)
            logging.info(f"Updated {xml_file_path} for location {location_id}.")
        except Exception as e:
            logging.error(f"Error saving the modified XML file {xml_file_path}: {e}")
            continue
        step_start_time = log_step_time(step_start_time, f"Saving XML file {xml_file_path}")

        # Add the unpacked folder to the list of folders to be repacked later
        unpacked_folders_to_repack.append(unpack_folder)

    # Step 11: Repack all modified folders using pc-re5.bat
    logging.info("Starting to repack modified folders...")
    step_start_time = time.time()
    for unpack_folder in unpacked_folders_to_repack:
        try:
            subprocess.run([os.path.join(arc_folder, 'pc-re5.bat'), unpack_folder], check=True)
            logging.info(f"Repacked {unpack_folder} successfully.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error repacking {unpack_folder}: {e}")

        # Clean up the unpacked folder after repacking
        try:
            shutil.rmtree(unpack_folder)
            logging.info(f"Cleaned up unpacked folder {unpack_folder}.")
        except Exception as e:
            logging.error(f"Error cleaning up folder {unpack_folder}: {e}")
    step_start_time = log_step_time(step_start_time, "Repacking folders")

    # Log the total time it took to run the program
    end_time = time.time()
    duration = end_time - start_time
    logging.info(f"Program completed in {duration:.2f} seconds.")

# Example usage
input_file = 'input.json'  # JSON file containing locations and ItemIDs
arc_folder = 'Archive'  # Folder containing the .arc files and pc-re5.bat
mapping_file = 'location_mapping.json'  # External JSON file containing location-to-file mappings

update_item_ids(input_file, arc_folder, mapping_file)
