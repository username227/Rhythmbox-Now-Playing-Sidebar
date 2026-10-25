# Rhythmbox-Now-Playing-Sidebar
A plugin to add a "Now Playing" box to Rhythmbox music player

# Features
- Adds a "Now Playing" field in the bottom half of the left sidebar.
- This plugin is not compatible with the "Play Queue in Side Pane" option in the View menu. If that option is selected, the "Now Playing" sidebar will automatically hide.
- Contains expanded, clearly visible album artwork, with track title, artist(s), and album under the album artwork.
- Contains an adjustable, horizontal bar dividing the Now Playing sidebar from the Library sidebar.

# Installation
Install the albumshuffle folder into either `/usr/lib/rhythmbox/plugins` or `~/.local/share/rhythmbox/plugins`. <p>
For the Flatpak version, install it into `~/.var/app/org.gnome.Rhythmbox3/data/rhythmbox/plugins`. <p>
In Rhythmbox, go to Preferences > Plugins and click "Continuous Album Shuffle" to activate.


# Full Disclosure
  I am not a developer and am not formally trained in computer programming. AI was used to assist in the writing of the code based on my specifications, testing, and feedback. I have tested various development versions on  Arch Linux with Rhythmbox 3.5.1. I have not tested the plugin on other distributions. Reviews and improvements to the code base, as well as additional feature requests, are welcome.

## Please Note
  The plugin is python-based. The issues regarding the breaking of the python-based Rhythmbox plugins was well known, and they were broken in the past for a significant amount of time. Those upstream issues appear to have been rectified now. However, future changes of  Rhythmbox or its dependencies could cause changes that affect this plugin, particularly if those changes break python-loader. Hopefully this will not happen, but if it does, this plugin could break.
