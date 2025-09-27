import json
import os
import logging

logger = logging.getLogger(__name__)

_config = None

def load_config(config_path="config.json"):
    """Load configuration from JSON file with validation"""
    global _config
    
    if _config is not None:
        return _config
    
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            _config = json.load(f)
        logger.info(f"Configuration loaded successfully from {config_path}")
        return _config
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise

def get_config():
    """Get the global configuration object"""
    if _config is None:
        return load_config()
    return _config

def validate_config():
    """Validate that all required configuration keys are present"""
    config = get_config()
    
    required_keys = {
        "reddit": ["client_id", "client_secret", "user_agent", "reddit_subreddits", "posts_limit"],
        "own_sitemap_url": str,
        "competitor_sitemaps": list
    }
    
    # Validate reddit configuration
    if "reddit" not in config:
        logger.error("'reddit' section missing from configuration")
        return False
    
    for key in required_keys["reddit"]:
        if key not in config["reddit"]:
            logger.error(f"Missing reddit config key: {key}")
            return False
    
    # Validate sitemap configuration
    if "own_sitemap_url" not in config:
        logger.error("'own_sitemap_url' missing from configuration")
        return False
    
    if "competitor_sitemaps" not in config or not isinstance(config["competitor_sitemaps"], list):
        logger.error("'competitor_sitemaps' missing or not a list")
        return False
    
    logger.info("Configuration validation passed")
    return True

def ensure_data_directory():
    """Ensure the data directory exists"""
    data_dir = "data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        logger.info(f"Created data directory: {data_dir}")
    return data_dir