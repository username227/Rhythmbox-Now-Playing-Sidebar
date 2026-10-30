# Rhythmbox-Now-Playing-Sidebar
A plugin to add a "Now Playing" box to Rhythmbox music player

<img width="1920" height="1080" alt="Screenshot from 2026-10-28 22-02-54" src="https://github.com/user-attachments/assets/8e32b707-1ee9-4d58-8615-d54db40051d5" />

# Features
- Adds a "Now Playing" field in the bottom half of the left sidebar.
- This plugin is not compatible with the "Play Queue in Side Pane" option in the View menu. If that option is selected, the "Now Playing" sidebar will automatically hide.
- Contains expanded, clearly visible album artwork, with track title, artist(s), and album under the album artwork.
- Contains an adjustable, horizontal bar dividing the Now Playing sidebar from the Library sidebar.

# Installation
For a **user-level installation**, copy the plugin folder into:

`~/.local/share/rhythmbox/plugins/`

For a **system-wide installation**, the location depends on your distribution:

- **Arch Linux:** `/usr/lib/rhythmbox/plugins/`
- **Debian/Ubuntu/Mint (x86_64):** `/usr/lib/x86_64-linux-gnu/rhythmbox/plugins/`
- **Debian/Ubuntu/Mint (ARM64):** `/usr/lib/aarch64-linux-gnu/rhythmbox/plugins/`

For **Flatpak**, use:

`~/.var/app/org.gnome.Rhythmbox3/data/rhythmbox/plugins/`

Restart Rhythmbox, open **Preferences → Plugins**, and enable the plugin.


# Full Disclosure
  I am not a developer and am not formally trained in computer programming. AI was used to assist in the writing of the code based on my specifications, testing, and feedback. I have tested various development versions on  Arch Linux with Rhythmbox 3.5.1. I have not tested the plugin on other distributions. Reviews and improvements to the code base, as well as additional feature requests, are welcome.

## Please Note
  The plugin is python-based. The issues regarding the breaking of the python-based Rhythmbox plugins was well known, and they were broken in the past for a significant amount of time. Those upstream issues appear to have been rectified now. However, future changes of  Rhythmbox or its dependencies could cause changes that affect this plugin, particularly if those changes break python-loader. Hopefully this will not happen, but if it does, this plugin could break.
