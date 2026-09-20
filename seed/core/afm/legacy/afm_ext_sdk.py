##### # AFM_ext_sdk.py - Made by Oracle & Carlos Clarke
# AFM External SDK Config Handler with Full Code Label Tracking
import os
import json
import shutil

# === PATH SETUP ===
BASE_DIR = "C:/AFM"
EXTRACTED_SDK_DIR = "C:/AFM/sdk_extracted"
CONFIGS_DIR = os.path.join(BASE_DIR, "configs")
COGNITIVE_SERVICES_DIR = os.path.join(CONFIGS_DIR, "cognitive_services")
DIGITAL_TWINS_DIR = os.path.join(CONFIGS_DIR, "digital_twins")
TRANSFORMERS_DIR = os.path.join(CONFIGS_DIR, "transformers")
MAX_NESTING_DEPTH = 5

# Ensure directory structure
for d in [COGNITIVE_SERVICES_DIR, DIGITAL_TWINS_DIR, TRANSFORMERS_DIR]:
    os.makedirs(d, exist_ok=True)


# === UTILITY ===
def get_directory_depth(path):
    return len(path.strip(os.sep).split(os.sep))


# === TYPE DETERMINATION ===
def determine_config_type(config_data):
    print("# === DETERMINE CONFIG TYPE ===")
    if "cognitive_service" in config_data or "api_endpoint" in config_data:
        print("# Type: Cognitive Service\n")
        return "cognitive_service"
    elif "node_id" in config_data or "container_type" in config_data:
        print("# Type: Digital Twin\n")
        return "digital_twin"
    elif "security_patch" in config_data or "optimization_level" in config_data:
        print("# Type: Transformer\n")
        return "transformer"
    else:
        print("# Type: Unknown\n")
        return "unknown"


# === DIRECTORY CREATION ===
def create_config_directory(config_type, config_name):
    print(f"# === CREATE CONFIG DIRECTORY for [{config_type.upper()}] ===")

    if config_type == "cognitive_service":
        target_dir = os.path.join(COGNITIVE_SERVICES_DIR, config_name)
    elif config_type == "digital_twin":
        target_dir = os.path.join(DIGITAL_TWINS_DIR, config_name)
    elif config_type == "transformer":
        target_dir = os.path.join(TRANSFORMERS_DIR, config_name)
    else:
        print("# Skipping unknown config type.")
        return None

    if get_directory_depth(target_dir) > MAX_NESTING_DEPTH:
        print(f"# Skipped: Depth > {MAX_NESTING_DEPTH}")
        return None

    if os.path.exists(target_dir):
        print(f"# Exists: {target_dir}")
        return target_dir

    os.makedirs(target_dir, exist_ok=True)
    print(f"# Created: {target_dir}\n")
    return target_dir


# === LOGIC EXECUTION HANDLER ===
def handle_logic(config_data):
    config_type = determine_config_type(config_data)

    if config_type == "cognitive_service":
        handle_cognitive_service(config_data)
    elif config_type == "digital_twin":
        handle_digital_twin(config_data)
    elif config_type == "transformer":
        handle_transformer(config_data)
    else:
        print("# Unhandled config type.")


# === MODULES: HANDLERS ===


def handle_cognitive_service(config_data):
    print("# === HANDLE COGNITIVE SERVICE ===")
    if "api_endpoint" in config_data:
        print(f"# Connecting to API: {config_data['api_endpoint']}")
    if "model_type" in config_data:
        print(f"# Initializing model: {config_data['model_type']}")
    print("")


def handle_digital_twin(config_data):
    print("# === HANDLE DIGITAL TWIN ===")
    if "node_id" in config_data:
        print(f"# Initializing node: {config_data['node_id']}")
    if "container_type" in config_data:
        print(f"# Setting up container: {config_data['container_type']}")
    print("")


def handle_transformer(config_data):
    print("# === HANDLE TRANSFORMER ===")
    if "security_patch" in config_data:
        print(f"# Applying patch: {config_data['security_patch']}")
    if "optimization_level" in config_data:
        print(f"# Optimizing system: {config_data['optimization_level']}")
    print("")


# === FILE PROCESSING ===
def process_config_file(file_path):
    print("# === PROCESS CONFIG FILE ===")
    print(f"# Path: {file_path}")
    try:
        with open(file_path, "r") as f:
            config_data = json.load(f)
    except Exception as e:
        print(f"# Failed to read/parse: {e}")
        return

    config_name = os.path.splitext(os.path.basename(file_path))[0]
    config_type = determine_config_type(config_data)
    create_config_directory(config_type, config_name)
    handle_logic(config_data)


# === MAIN PROCESS LOOP ===
def process_sdk_configs():
    print("# === STARTING SDK CONFIG PROCESSOR ===")
    for root, dirs, files in os.walk(EXTRACTED_SDK_DIR):
        for file in files:
            if file.endswith(".json"):
                file_path = os.path.join(root, file)
                process_config_file(file_path)


# === START ===
if __name__ == "__main__":
    process_sdk_configs()


def run():
    print("🛠️ Auto-generated run() for module: afm_ext_sdk.py")
