# config_loader.py
import re
import yaml


def parse_size_to_bytes(size_str: str) -> int:
    """
    Converts human-readable strings like '500MB' or '50MB' into raw integer bytes.
    Supports B, KB, MB, GB.
    """
    if isinstance(size_str, int):
        return size_str

    match = re.match(r"^(\d+)\s*(MB|GB|KB|B)$", size_str.strip().upper())
    if not match:
        raise ValueError(f"Invalid capped collection size format: {size_str}")

    value, unit = match.groups()
    value = int(value)

    units = {
        "B": 1,
        "KB": 1024,
        "MB": 1024 * 1024,
        "GB": 1024 * 1024 * 1024
    }
    return value * units[unit]


def load_config(file_path: str = "config.yaml") -> dict:
    """
    Loads the YAML configuration file and injects calculated byte sizes
    for capped database collections.
    """
    try:
        with open(file_path, 'r') as file:
            config = yaml.safe_load(file)

        # Programmatically attach byte conversions for the database initialization layer
        capped = config['database']['capped_collections']
        capped['system_logs_bytes'] = parse_size_to_bytes(capped['system_logs_max_size'])
        capped['health_checks_bytes'] = parse_size_to_bytes(capped['health_checks_max_size'])

        return config
    except FileNotFoundError:
        raise FileNotFoundError(f"Critical Error: Configuration file not found at {file_path}")
    except Exception as e:
        raise RuntimeError(f"Critical Error parsing configuration matrix: {e}")


if __name__ == "__main__":
    # Quick self-test to verify configuration parsing utility functions work smoothly
    cfg = load_config()
    print("[SUCCESS] Configurations successfully parsed and decoupled.")
    print(f"-> Target Simulator: {cfg['simulator']['base_url']}")
    print(f"-> System Logs Cap Allocation: {cfg['database']['capped_collections']['system_logs_bytes']} Bytes")
