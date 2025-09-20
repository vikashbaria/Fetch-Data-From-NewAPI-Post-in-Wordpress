# 📰 News API → WordPress Importer (Python)

A Python script to **fetch articles from [News API]** and automatically publish them to a **WordPress site** via REST API using Application Password authentication.  

✅ Supports multiple API keys with automatic failover.  
✅ Uploads featured images from articles.  
✅ Extracts tags and assigns categories automatically.  
✅ Skips duplicates using a JSON tracker.  

---

![Pakalertpress Home Page](https://raw.githubusercontent.com/vikashbaria/Fetch-Data-From-NewAPI-Post-in-Wordpress/refs/heads/main/Pakalertpress%20Home%20Page.JPG)


## ✨ Features

- 🔑 **Multiple API keys** with auto failover when quota is reached.  
- 🖼️ **Featured images** uploaded directly to WordPress.  
- 🏷️ **Tags auto-generated** from article keywords.  
- 📂 **Categories auto-detected** (Politics, Sports, Technology, Crime, etc.).  
- 🛡️ **Duplicate prevention** using `imported_ids.json`.  
- ⚡ Lightweight and easy to configure.  

---




## 🛠️ Requirements

- Python **3.8+**  
- WordPress site with:
  - REST API enabled (default in WP 5.0+)  
  - Application Passwords plugin (if WP < 5.6) or built-in support  
- Installed dependencies:
