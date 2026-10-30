"""Now Playing Sidebar: Rhythmbox 3.5.x GTK3 sidebar integration.

Version 1.3.0: adds an informational elapsed/total clock, with optional
read-only preview of a pending Session Restore checkpoint. This plugin never
starts, stops, pauses, or seeks playback.
"""
import json
import logging
import os
import traceback

from gi.repository import GObject, Gio, GLib, Gtk, GdkPixbuf, Peas, RB

LOG = logging.getLogger('rhythmbox-now-playing-sidebar')
DIAGNOSTICS = os.path.join(GLib.get_user_cache_dir(), 'rhythmbox', 'nowplayingsidebar.log')
SCHEMA = 'org.gnome.rhythmbox'
CONFIG = os.path.join(GLib.get_user_config_dir(), 'rhythmbox', 'nowplayingsidebar.json')
STATE = os.path.join(os.environ.get('XDG_STATE_HOME', os.path.expanduser('~/.local/state')),
                     'rhythmbox-session-restore', 'pending-resume.json')


def note(message):
    try:
        os.makedirs(os.path.dirname(DIAGNOSTICS), exist_ok=True)
        with open(DIAGNOSTICS, 'a', encoding='utf-8') as stream:
            stream.write(message + '\n')
    except OSError:
        pass
    LOG.warning('%s', message)


class NowPlayingSidebar(GObject.Object, Peas.Activatable):
    __gtype_name__ = 'NowPlayingSidebarPlugin'
    object = GObject.Property(type=GObject.Object)

    def __init__(self):
        super().__init__()
        self.shell = self.player = self.settings = self.art_store = None
        self.paned = self.queue = self.holder = self.panel = None
        self.picture = self.title = self.artist = self.album = self.track_clock = None
        self.song_handler = self.setting_handler = self.art_handler = None
        self.size_handler = self.position_handler = None
        self.entry = self.art_key = self.pixbuf = None
        self.generation = 0
        self.initial_position_done = False
        self.desired_height = self._read_height()
        self.save_source = self.clock_source_id = None
        self.last_image_size = 0
        self.preview_uri = None

    def _read_height(self):
        try:
            with open(CONFIG, encoding='utf-8') as f:
                return max(130, min(900, int(json.load(f)['height'])))
        except (OSError, ValueError, KeyError, TypeError):
            return 330

    def _save_height(self):
        self.save_source = None
        if self.paned is None or self.queue is None or self.settings.get_boolean('queue-as-sidebar'):
            return GLib.SOURCE_REMOVE
        try:
            os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
            with open(CONFIG, 'w', encoding='utf-8') as f:
                json.dump({'height': self.desired_height}, f)
        except OSError:
            LOG.exception('Unable to save sidebar height')
        return GLib.SOURCE_REMOVE

    def _walk(self, widget):
        yield widget
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                yield from self._walk(child)

    def _find_source_paned(self):
        window = self.shell.props.window
        widgets = list(self._walk(window))
        trees = [w for w in widgets if GObject.type_name(w.__gtype__) == 'RBDisplayPageTree']
        note('Tree widgets found: %d; GTK paned widgets: %d' %
             (len(trees), sum(isinstance(w, Gtk.Paned) for w in widgets)))
        for widget in trees:
            parent = widget.get_parent()
            while parent is not None and parent is not window:
                if (isinstance(parent, Gtk.Paned) and
                        parent.get_orientation() == Gtk.Orientation.VERTICAL and
                        parent.get_child1() is not None and parent.get_child2() is not None):
                    note('Found source/queue paned via tree ancestor')
                    return parent
                parent = parent.get_parent()
        for w in widgets:
            if (isinstance(w, Gtk.Paned) and
                    w.get_orientation() == Gtk.Orientation.VERTICAL and
                    w.get_child1() and w.get_child2()):
                if any(child in trees for child in self._walk(w.get_child1())):
                    note('Found source/queue paned through first child')
                    return w
        note('Unable to find a matching vertical sidebar paned')
        return None

    def _label(self, css_name):
        label = Gtk.Label(xalign=0.5)
        label.set_justify(Gtk.Justification.CENTER)
        label.set_line_wrap(True)
        label.set_line_wrap_mode(2)
        label.set_ellipsize(0)
        label.set_max_width_chars(24)
        label.set_hexpand(True)
        label.get_style_context().add_class(css_name)
        return label

    def _make_panel(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        outer.set_margin_start(10)
        outer.set_margin_end(10)
        outer.set_margin_top(8)
        outer.set_margin_bottom(9)
        heading = Gtk.Label(label='Now Playing', xalign=0)
        heading.get_style_context().add_class('heading')
        outer.pack_start(heading, False, False, 4)
        self.picture = Gtk.Image.new_from_icon_name('rhythmbox-missing-artwork', Gtk.IconSize.DIALOG)
        self.picture.set_halign(Gtk.Align.CENTER)
        self.picture.set_valign(Gtk.Align.START)
        outer.pack_start(self.picture, False, False, 0)
        self.track_clock = Gtk.Label(label='--:-- / --:--')
        self.track_clock.set_xalign(0.5)
        self.track_clock.get_style_context().add_class('dim-label')
        self.track_clock.set_tooltip_text('Elapsed / total track time')
        outer.pack_start(self.track_clock, False, False, 5)
        self.title = self._label('title')
        self.title.set_markup('<b>Not Playing</b>')
        self.artist = self._label('artist')
        self.album = self._label('album')
        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        details.set_margin_top(5)
        for label in (self.title, self.artist, self.album):
            details.pack_start(label, False, False, 0)
        outer.pack_start(details, False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.NONE)
        scroll.set_propagate_natural_height(False)
        scroll.add(outer)
        self.panel = scroll
        self.panel.connect('size-allocate', self._on_panel_size)
        return scroll

    def do_activate(self):
        note('Activating Now Playing Sidebar 1.3.0')
        try:
            self.shell = self.object
            self.player = self.shell.props.shell_player
            self.settings = Gio.Settings.new(SCHEMA)
            self.paned = self._find_source_paned()
            if self.paned is None:
                note('Rhythmbox source/queue splitter not found; no UI changed')
                return
            note('Found GTK paned; attaching Now Playing')
            self.queue = self.paned.get_child2()
            if self.queue is None:
                note('Queue child not found; no UI changed')
                self.paned = None
                return
            self.holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.holder.set_no_show_all(True)
            panel = self._make_panel()
            self.paned.remove(self.queue)
            note('Detached original queue widget')
            self.holder.pack_start(self.queue, True, True, 0)
            self.holder.pack_start(panel, True, True, 0)
            self.paned.pack2(self.holder, True, True)
            note('Attached replacement holder')
            self.holder.show()
            panel.show_all()
            self.art_store = RB.ExtDB(name='album-art')
            self.art_handler = self.art_store.connect('added', self._art_added)
            self.song_handler = self.player.connect('playing-song-changed', self._song_changed)
            self.setting_handler = self.settings.connect('changed::queue-as-sidebar', self._queue_changed)
            self.size_handler = self.paned.connect('size-allocate', self._on_size)
            self.position_handler = self.paned.connect('notify::position', self._on_position)
            self._queue_changed(self.settings, 'queue-as-sidebar')
            try:
                entry = self.player.get_playing_entry()
            except Exception:
                entry = None
            self._song_changed(self.player, entry)
            self.clock_source_id = GLib.timeout_add_seconds(1, self._refresh_track_clock)
            self._refresh_track_clock()
            note('Now Playing panel attached successfully')
        except Exception as exc:
            note('ACTIVATION FAILED: %r\n%s' % (exc, traceback.format_exc()))
            LOG.exception('Unable to activate Now Playing Sidebar')
            self.do_deactivate()

    def _queue_changed(self, _settings, _key):
        if self.panel is None or self.queue is None or self.paned is None:
            return
        is_queue = self.settings.get_boolean('queue-as-sidebar')
        self.panel.set_visible(not is_queue)
        self.holder.set_visible(True)
        if not is_queue:
            self.initial_position_done = False
            GLib.idle_add(self._restore_position)
            self._resize_art()

    def _restore_position(self):
        if self.paned is None or self.settings.get_boolean('queue-as-sidebar'):
            return GLib.SOURCE_REMOVE
        available = self.paned.get_allocated_height()
        if available > 250:
            self.paned.set_position(max(85, available - min(self.desired_height, available - 85)))
            self.initial_position_done = True
        return GLib.SOURCE_REMOVE

    def _on_size(self, _widget, allocation):
        if not self.initial_position_done and allocation.height > 250:
            GLib.idle_add(self._restore_position)
        self._resize_art()

    def _on_position(self, _widget, _pspec):
        if not self.initial_position_done or self.settings.get_boolean('queue-as-sidebar'):
            return
        height = self.paned.get_allocated_height() - self.paned.get_position()
        if height < 90:
            return
        self.desired_height = height
        if self.save_source is not None:
            GLib.source_remove(self.save_source)
        self.save_source = GLib.timeout_add(600, self._save_height)

    def _on_panel_size(self, _widget, _allocation):
        self._resize_art()

    def _resize_art(self):
        if self.panel is None or self.picture is None:
            return
        width = self.panel.get_allocated_width()
        height = self.panel.get_allocated_height()
        size = max(32, min(width - 20, height - 145, 420))
        if size == self.last_image_size:
            return
        self.last_image_size = size
        if self.pixbuf is not None:
            scaled = self.pixbuf.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
            if scaled is not None:
                self.picture.set_from_pixbuf(scaled)
        else:
            self.picture.set_pixel_size(min(size, 96))

    def _text(self, label, value):
        value = value or ''
        safe = GLib.markup_escape_text(value)
        if label is self.title:
            label.set_markup('<b>' + safe + '</b>')
        elif label is self.album:
            label.set_markup('<i>' + safe + '</i>')
        else:
            label.set_text(value)
        label.set_tooltip_text(value if len(value) > 35 else None)

    def _song_changed(self, _player, entry):
        self.entry = entry
        self.art_key = None
        self.pixbuf = None
        self.last_image_size = 0
        self.generation += 1
        self.picture.set_from_icon_name('rhythmbox-missing-artwork', Gtk.IconSize.DIALOG)
        if entry is None:
            self.title.set_markup('<b>Not Playing</b>')
            self._text(self.artist, '')
            self._text(self.album, '')
            return
        self._text(self.title, entry.get_string(RB.RhythmDBPropType.TITLE))
        self._text(self.artist, entry.get_string(RB.RhythmDBPropType.ARTIST))
        self._text(self.album, entry.get_string(RB.RhythmDBPropType.ALBUM))
        self._resize_art()
        try:
            key = entry.create_ext_db_key(RB.RhythmDBPropType.ALBUM)
            generation = self.generation
            self.art_store.request(key, lambda key, skey, filename, data: self._art_received(generation, skey, data))
        except Exception:
            LOG.exception('Could not request artwork for playing entry')

    @staticmethod
    def _format_track_time(seconds):
        seconds = max(0, int(seconds))
        minutes, sec = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f'{hours}:{minutes:02}:{sec:02}' if hours else f'{minutes}:{sec:02}'

    def _pending_resume(self):
        try:
            with open(STATE, encoding='utf-8') as f:
                data = json.load(f)
            if (data.get('pid') != os.getpid() or
                    not isinstance(data.get('uri'), str)):
                return None
            return data
        except (OSError, ValueError, TypeError):
            return None

    def _refresh_track_clock(self):
        if self.player is None or self.track_clock is None:
            return GLib.SOURCE_REMOVE
        try:
            pending = self._pending_resume()
            actual = self.player.get_playing_entry()
            if actual is not None:
                uri = actual.get_string(RB.RhythmDBPropType.LOCATION)
                if pending and pending.get('uri') == uri:
                    elapsed = int(pending.get('position', 0))
                else:
                    elapsed = int(self.player.get_playing_time()[1])
                if self.preview_uri is not None:
                    self.preview_uri = None
                entry = actual
                if (self.entry is None or
                        self.entry.get_string(RB.RhythmDBPropType.LOCATION) != uri):
                    self._song_changed(self.player, entry)
            elif pending:
                uri = pending['uri']
                entry = self.shell.props.db.entry_lookup_by_location(uri)
                elapsed = int(pending.get('position', 0))
                if entry is not None and self.preview_uri != uri:
                    self.preview_uri = uri
                    self._song_changed(self.player, entry)
            else:
                entry = None
                elapsed = 0
                if self.preview_uri is not None:
                    self.preview_uri = None
                    self._song_changed(self.player, None)
            if entry is not None:
                total = int(entry.get_ulong(RB.RhythmDBPropType.DURATION))
                self.track_clock.set_text('%s / %s' % (
                    self._format_track_time(elapsed), self._format_track_time(total)))
            else:
                self.track_clock.set_text('--:-- / --:--')
        except Exception:
            LOG.exception('Unable to refresh elapsed/total track clock')
        return GLib.SOURCE_CONTINUE

    def _art_received(self, generation, key, data):
        if generation != self.generation or self.entry is None or data is None:
            return
        try:
            if self.shell.props.db.entry_matches_ext_db_key(self.entry, key):
                self.art_key = key
                self.pixbuf = data
                self.last_image_size = 0
                self._resize_art()
        except Exception:
            LOG.exception('Unable to use requested album artwork')

    def _art_added(self, _store, key, _filename, data):
        self._art_received(self.generation, key, data)

    def do_deactivate(self):
        if self.clock_source_id is not None:
            GLib.source_remove(self.clock_source_id)
            self.clock_source_id = None
        if self.save_source is not None:
            GLib.source_remove(self.save_source)
            self.save_source = None
            self._save_height()
        for obj, attr in ((self.player, 'song_handler'), (self.settings, 'setting_handler'),
                          (self.art_store, 'art_handler'), (self.paned, 'size_handler'),
                          (self.paned, 'position_handler')):
            handler = getattr(self, attr)
            if obj is not None and handler is not None:
                try:
                    obj.disconnect(handler)
                except (TypeError, RuntimeError):
                    pass
            setattr(self, attr, None)
        if self.paned is not None and self.queue is not None and self.holder is not None:
            try:
                if self.queue.get_parent() is self.holder:
                    self.holder.remove(self.queue)
                    if self.holder.get_parent() is self.paned:
                        self.paned.remove(self.holder)
                    self.paned.pack2(self.queue, True, True)
                elif self.holder.get_parent() is self.paned:
                    self.paned.remove(self.holder)
            except Exception:
                LOG.exception('Unable to restore original sidebar')
        self.paned = self.queue = self.holder = self.panel = None
        self.picture = self.title = self.artist = self.album = self.track_clock = None
        self.player = self.settings = self.art_store = self.shell = None
        self.entry = self.art_key = self.pixbuf = None
