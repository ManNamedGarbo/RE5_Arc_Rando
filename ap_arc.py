import json
import os
import subprocess
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

def load_location_mapping(mapping_file="location_mapping.json"):
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
        print(f"Error loading location mapping {mapping_file}: {e}")  # Print the error, instead of only logging it.
        raise

def process_arc_file(arc_folder, arc_file, location_id, new_item_id):
    """Process an individual .arc file and update its corresponding item ID."""
    arc_path = os.path.join(arc_folder, arc_file)
    
    # Unpack the .arc file if not already unpacked
    unpack_folder = os.path.splitext(arc_file)[0]
    if not os.path.exists(unpack_folder):
        logging.info(f"Unpacking {arc_file}...")
        subprocess.run(['pc-re5.bat', arc_path], check=True)
    
    # Find the XML file inside the unpacked folder
    xml_file_path = os.path.join('Archive', unpack_folder, 'stage', unpack_folder, f'soft\{unpack_folder}_item.lot.xml')
    
    # Open and modify the XML file
    if not os.path.exists(xml_file_path):
        logging.error(f"XML file {xml_file_path} not found. Skipping...")
        return
    
    logging.info(f"Modifying ItemID for {location_id} in {xml_file_path}...")
    try:
        with open(xml_file_path, 'r') as file:
            content = file.read()

        # Find the location in the XML and update the ItemID
        location_start = content.find(f'<string name="mUnitClass" value="{location_id}"/>')
        if location_start == -1:
            logging.error(f"Location {location_id} not found in {xml_file_path}. Skipping...")
            return
        
        # Find the ItemID line inside this classref
        item_id_start = content.find('<u16 name="ItemId" value="', location_start)
        item_id_end = content.find('"', item_id_start + len('<u16 name="ItemId" value="'))
        if item_id_start == -1 or item_id_end == -1:
            logging.error(f"ItemId for {location_id} not found in {xml_file_path}. Skipping...")
            return

        # Replace the ItemID with the new value
        new_content = content[:item_id_start + len('<u16 name="ItemId" value="')] + str(new_item_id) + content[item_id_end:]

        # Write the modified content back to the file
        with open(xml_file_path, 'w') as file:
            file.write(new_content)
        
        logging.info(f"Updated ItemID for {location_id} to {new_item_id} in {xml_file_path}.")
        
        # Repack the modified unpacked folder back into the .arc file
        logging.info(f"Repacking {unpack_folder} back into .arc file...")
        subprocess.run(['pc-re5.bat', os.path.join(arc_folder, unpack_folder)], check=True)
        logging.info(f"Repacked {unpack_folder} back into its .arc file.")

    except Exception as e:
        logging.error(f"Error modifying {xml_file_path}: {e}")

def update_item_ids(input_file, arc_folder, mapping_file, output_folder):
    """Main function to update Item IDs in the XML files."""
    try:
        # Step 1: Load input data (location ID and new ItemID)
        with open(input_file, 'r') as f:
            input_data = json.load(f)  # This is where input_data is loaded from the file

        logging.info(f"Loaded {len(input_data)} entries from {input_file}.")  # Log how many entries were loaded

        # Step 2: Load location-to-file mapping from the external JSON file using the existing function
        logging.info("Starting to load location mappings...")
        step_start_time = time.time()
        try:
            location_to_file_mapping = load_location_mapping(mapping_file)  # Load the location-to-file mapping
        except Exception as e:
            logging.error(f"Failed to load location mappings: {e}")
            print(f"Error loading location mapping: {e}")  # Print the error, instead of only logging it
            return  # Exit if loading the mapping fails

        step_start_time = log_step_time(step_start_time, "Loading location mappings")

        # Step 3: Loop through input data (locations and ItemIDs)
        for i in range(0, len(input_data), 2):  # Fixed the loop range
            location_id = input_data[i]  # Location ID (e.g., "uWp13")
            new_item_id = input_data[i + 1]  # New ItemID (e.g., 769)

            logging.info(f"Processing location {location_id} with new ItemID {new_item_id}...")

            # Step 4: Determine which file corresponds to this location ID
            if location_id not in location_to_file_mapping:
                logging.warning(f"No output file mapped for location {location_id}. Skipping...")
                continue  # Skip if there's no file mapped for this location
            
            arc_file = location_to_file_mapping[location_id]  # Get the .arc file from the mapping
            arc_path = os.path.join(arc_folder, arc_file)  # Full path to the .arc file

            # Check if the .arc file exists
            if not os.path.exists(arc_path):
                logging.error(f"The file {arc_file} does not exist in the specified folder. Skipping...")
                continue

            # Process the arc file and modify the corresponding XML
            process_arc_file(arc_folder, arc_file, location_id, new_item_id)

        logging.info("Process completed successfully.")
    
    except Exception as e:
        logging.error(f"Error during the update process: {e}")
        print(f"Error: {e}")

    # Clean up the Archive folder of any remaining unpacked folders (after the repacking step)
    logging.info("Cleaning up the Archive folder of any remaining unpacked folders...")

    for folder in os.listdir(arc_folder):
        folder_path = os.path.join(arc_folder, folder)
        if os.path.isdir(folder_path) and folder != "Archive":
            logging.info(f"Removing unpacked folder {folder_path}...")
            shutil.rmtree(folder_path)  # Delete the folder and its contents
    logging.info("Archive folder cleanup completed.")
    
if __name__ == "__main__":
    input_file = 'input.json'  # JSON file containing locations and ItemIDs
    arc_folder = 'Archive'  # Folder containing the .arc files and pc-re5.bat
    mapping_file = 'location_mapping.json'  # External JSON file containing location-to-file mappings
    output_folder = 'output'  # Folder to store the newly created .arc files

    start_time = time.time()
    update_item_ids(input_file, arc_folder, mapping_file, output_folder)
    duration = time.time() - start_time
    logging.info(f"Program completed in {duration:.2f} seconds.")
    print(f"Program completed in {duration:.2f} seconds.")
