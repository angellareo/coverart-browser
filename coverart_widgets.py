# -*- Mode: python; coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
#
# Copyright (C) 2012 - fossfreedom
# Copyright (C) 2012 - Agustin Carrasco
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.

from gi.repository import RB
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gio
from gi.repository import Notify
import cairo

from coverart_browser_prefs import GSetting
from coverart_external_plugins import ExternalPlugin
import rb


def enum(**enums):
    return type('Enum', (object,), enums)


class OptionsWidget(Gtk.Widget):
    def __init__(self, *args, **kwargs):
        super(OptionsWidget, self).__init__(*args, **kwargs)
        self._controller = None

    @property
    def controller(self):
        return self._controller

    @controller.setter
    def controller(self, controller):
        if self._controller:
            # disconnect signals
            self._controller.disconnect(self._options_changed_id)
            self._controller.disconnect(self._current_key_changed_id)
            self._controller.disconnect(self._update_image_changed_id)

        self._controller = controller

        # connect signals
        self._options_changed_id = self._controller.connect('notify::options',
                                                            self._update_options)
        self._current_key_changed_id = self._controller.connect(
            'notify::current-key', self._update_current_key)
        self._update_image_changed_id = self._controller.connect(
            'notify::update-image', self._update_image)
        self._visible_changed_id = self._controller.connect(
            'notify::enabled', self._update_visibility)

        # update the menu and current key
        self.update_options()
        self.update_current_key()

    def _update_visibility(self, *args):
        self.set_visible(self._controller.enabled)

    def _update_options(self, *args):
        self.update_options()

    def update_options(self):
        pass

    def _update_current_key(self, *args):
        self.update_current_key()

    def update_current_key():
        pass

    def _update_image(self, *args):
        self.update_image()

    def update_image(self):
        pass

    def calc_popup_position(self, widget):
        # this calculates the popup positioning - algorithm taken
        # from Gtk3.8 gtk/gtkmenubutton.c

        toplevel = self.get_toplevel()
        toplevel.set_type_hint(Gdk.WindowTypeHint.DROPDOWN_MENU)

        menu_req, pref_req = widget.get_preferred_size()
        align = widget.get_halign()
        direction = self.get_direction()
        window = self.get_window()

        screen = widget.get_screen()
        monitor_num = screen.get_monitor_at_window(window)
        if (monitor_num < 0):
            monitor_num = 0
        monitor = screen.get_monitor_workarea(monitor_num)

        allocation = self.get_allocation()

        ret, x, y = window.get_origin()
        x += allocation.x
        y += allocation.y

        if allocation.width - menu_req.width > 0:
            x += allocation.width - menu_req.width

        if ((y + allocation.height + menu_req.height) <= monitor.y + monitor.height):
            y += allocation.height
        elif ((y - menu_req.height) >= monitor.y):
            y -= menu_req.height
        else:
            y -= menu_req.height

        return x, y


class OptionsPopupWidget(OptionsWidget):
    # signals
    __gsignals__ = {
        'item-clicked': (GObject.SIGNAL_RUN_LAST, None, (str,))
    }

    def __init__(self, *args, **kwargs):
        OptionsWidget.__init__(self, *args, **kwargs)

        self._popup_menu = Gtk.Menu()

    def update_options(self):
        self.clear_popupmenu()

        for key in self._controller.options:
            self.add_menuitem(key)

    def update_current_key(self):
        # select the item if it isn't already
        item = self.get_menuitems()[self._controller.get_current_key_index()]

        if not item.get_active():
            item.set_active(True)

    def add_menuitem(self, label):
        '''
        add a new menu item to the popup
        '''
        if not self._first_menu_item:
            new_menu_item = Gtk.RadioMenuItem(label=label)
            self._first_menu_item = new_menu_item
        else:
            new_menu_item = Gtk.RadioMenuItem.new_with_label_from_widget(
                group=self._first_menu_item, label=label)

        new_menu_item.connect('toggled', self._fire_item_clicked)
        new_menu_item.show()

        self._popup_menu.append(new_menu_item)

    def get_menuitems(self):
        return self._popup_menu.get_children()

    def clear_popupmenu(self):
        '''
        reinitialises/clears the current popup menu and associated actions
        '''
        for menu_item in self._popup_menu:
            self._popup_menu.remove(menu_item)

        self._first_menu_item = None

    def _fire_item_clicked(self, menu_item):
        '''
        Fires the item-clicked signal if the item is selected, passing the
        given value as a parameter. Also updates the current value with the
        value of the selected item.
        '''
        if menu_item.get_active():
            self.emit('item-clicked', menu_item.get_label())

    def do_item_clicked(self, key):
        if self._controller:
            # inform the controller
            self._controller.option_selected(key)

    def _popup_callback(self, *args):
        x, y = self.calc_popup_position(self._popup_menu)

        return x, y, False, None

    def show_popup(self, align=True):
        '''
        show the current popup menu
        '''

        if align:
            self._popup_menu.popup(None, None, self._popup_callback, self, 0,
                                   Gtk.get_current_event_time())
        else:
            self._popup_menu.popup(None, None, None, None, 0,
                                   Gtk.get_current_event_time())

    def do_delete_thyself(self):
        self.clear_popupmenu()
        del self._popupmenu

class PressButton(Gtk.Button):
    button_relief = GObject.property(type=bool, default=False)

    def __init__(self, *args, **kwargs):
        super(PressButton, self).__init__(*args, **kwargs)

        gs = GSetting()
        setting = gs.get_setting(gs.Path.PLUGIN)
        setting.bind(gs.PluginKey.BUTTON_RELIEF, self,
                     'button_relief', Gio.SettingsBindFlags.GET)

        self.connect('notify::button-relief',
                     self.on_notify_button_relief)

    def on_notify_button_relief(self, *arg):
        if self.button_relief:
            self.set_relief(Gtk.ReliefStyle.NONE)
        else:
            self.set_relief(Gtk.ReliefStyle.HALF)

    def set_image(self, pixbuf):
        image = self.get_image()

        if not image:
            image = Gtk.Image()
            super(PressButton, self).set_image(image)

        if hasattr(self, "controller.enabled") and not self.controller.enabled:
            pixbuf = self._getBlendedPixbuf(pixbuf)

        self.get_image().set_from_pixbuf(pixbuf)

        self.on_notify_button_relief()

    def _getBlendedPixbuf(self, pixbuf):
        """Turn a pixbuf into a blended version of the pixbuf by drawing a
        transparent alpha blend on it."""
        pixbuf = pixbuf.copy()

        w, h = pixbuf.get_width(), pixbuf.get_height()
        surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32, pixbuf.get_width(), pixbuf.get_height())
        context = cairo.Context(surface)

        Gdk.cairo_set_source_pixbuf(context, pixbuf, 0, 0)
        context.paint()

        context.set_source_rgba(32, 32, 32, 0.4)
        context.set_line_width(0)
        context.rectangle(0, 0, w, h)
        context.fill()

        pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0, w, h)

        return pixbuf

class EnhancedButton(Gtk.ToggleButton):
    button_relief = GObject.property(type=bool, default=False)

    def __init__(self, *args, **kwargs):
        super(EnhancedButton, self).__init__(*args, **kwargs)

        gs = GSetting()
        setting = gs.get_setting(gs.Path.PLUGIN)
        setting.bind(gs.PluginKey.BUTTON_RELIEF, self,
                     'button_relief', Gio.SettingsBindFlags.GET)

        self.connect('notify::button-relief',
                     self.on_notify_button_relief)

    def on_notify_button_relief(self, *arg):
        if self.button_relief:
            self.set_relief(Gtk.ReliefStyle.NONE)
        else:
            self.set_relief(Gtk.ReliefStyle.HALF)


class PixbufButton(EnhancedButton):
    button_relief = GObject.property(type=bool, default=False)

    def __init__(self, *args, **kwargs):
        super(PixbufButton, self).__init__(*args, **kwargs)

    def set_image(self, pixbuf):
        image = self.get_image()

        if not image:
            image = Gtk.Image()
            super(PixbufButton, self).set_image(image)

        if hasattr(self, "controller.enabled") and not self.controller.enabled:
            pixbuf = self._getBlendedPixbuf(pixbuf)

        self.get_image().set_from_pixbuf(pixbuf)

        self.on_notify_button_relief()

    def _getBlendedPixbuf(self, pixbuf):
        """Turn a pixbuf into a blended version of the pixbuf by drawing a
        transparent alpha blend on it."""
        pixbuf = pixbuf.copy()

        w, h = pixbuf.get_width(), pixbuf.get_height()
        surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32, pixbuf.get_width(), pixbuf.get_height())
        context = cairo.Context(surface)

        Gdk.cairo_set_source_pixbuf(context, pixbuf, 0, 0)
        context.paint()

        context.set_source_rgba(32, 32, 32, 0.4)
        context.set_line_width(0)
        context.rectangle(0, 0, w, h)
        context.fill()

        pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0, w, h)

        return pixbuf


class PopupButton(PixbufButton, OptionsPopupWidget):
    __gtype_name__ = "PopupButton"

    # signals
    __gsignals__ = {
        'item-clicked': (GObject.SIGNAL_RUN_LAST, None, (str,))
    }

    def __init__(self, *args, **kwargs):
        '''
        Initializes the button.
        '''
        PixbufButton.__init__(self, *args, **kwargs)
        OptionsPopupWidget.__init__(self, *args, **kwargs)

        self._popup_menu.attach_to_widget(self, None)  # critical to ensure theming works
        self._popup_menu.connect('deactivate', self.popup_deactivate)

        # initialise some variables
        self._first_menu_item = None

    def popup_deactivate(self, *args):
        self.set_active(False)

    def update_image(self):
        super(PopupButton, self).update_image()
        self.set_image(self._controller.get_current_image())

    def update_current_key(self):
        super(PopupButton, self).update_current_key()

        # update the current image and tooltip
        self.set_image(self._controller.get_current_image())
        self.set_tooltip_text(self._controller.get_current_description())

    def do_button_press_event(self, event):
        '''
        when button is clicked, update the popup with the sorting options
        before displaying the popup
        '''
        if (event.button == Gdk.BUTTON_PRIMARY):
            self.show_popup()
            self.set_active(True)


class TextPopupButton(EnhancedButton, OptionsPopupWidget):
    __gtype_name__ = "TextPopupButton"

    # signals
    __gsignals__ = {
        'item-clicked': (GObject.SIGNAL_RUN_LAST, None, (str,))
    }

    def __init__(self, *args, **kwargs):
        '''
        Initializes the button.
        '''
        EnhancedButton.__init__(self, *args, **kwargs)
        OptionsPopupWidget.__init__(self, *args, **kwargs)

        self._popup_menu.attach_to_widget(self, None)  # critical to ensure theming works
        self._popup_menu.connect('deactivate', self.popup_deactivate)

        # initialise some variables
        self._first_menu_item = None

    def popup_deactivate(self, *args):
        self.set_active(False)

    def do_button_press_event(self, event):
        '''
        when button is clicked, update the popup with the sorting options
        before displaying the popup
        '''
        if (event.button == Gdk.BUTTON_PRIMARY):
            self.show_popup()
            self.set_active(True)


class MenuButton(PixbufButton, OptionsPopupWidget):
    __gtype_name__ = "MenuButton"

    # signals
    __gsignals__ = {
        'item-clicked': (GObject.SIGNAL_RUN_LAST, None, (str,))
    }

    def __init__(self, *args, **kwargs):
        '''
        Initializes the button.
        '''
        PixbufButton.__init__(self, *args, **kwargs)
        OptionsPopupWidget.__init__(self, *args, **kwargs)

        self._popup_menu.attach_to_widget(self, None)  # critical to ensure theming works
        self._popup_menu.connect('deactivate', self.popup_deactivate)
        self._states = {}

    def popup_deactivate(self, *args):
        self.set_active(False)

    def add_menuitem(self, key):
        '''
        add a new menu item to the popup
        '''

        label = key.label
        menutype = key.menutype
        typevalue = key.typevalue

        if menutype and menutype == 'separator':
            new_menu_item = Gtk.SeparatorMenuItem().new()
        elif menutype and menutype == 'check':
            new_menu_item = Gtk.CheckMenuItem(label=label)
            new_menu_item.set_active(typevalue)
            new_menu_item.connect('toggled', self._fire_item_clicked)
        else:
            new_menu_item = Gtk.MenuItem(label=label)
            new_menu_item.connect('activate', self._fire_item_clicked)

        new_menu_item.show()
        self._popup_menu.append(new_menu_item)

    def clear_popupmenu(self):
        '''
        reinitialises/clears the current popup menu and associated actions
        '''
        for menu_item in self._popup_menu:
            if isinstance(menu_item, Gtk.CheckMenuItem):
                self._states[menu_item.get_label()] = menu_item.get_active()
            self._popup_menu.remove(menu_item)

        self._first_menu_item = None

    def update_options(self):
        self.clear_popupmenu()

        for key in self._controller.options:
            self.add_menuitem(key)

        self._states = {}

    def _fire_item_clicked(self, menu_item):
        '''
        Fires the item-clicked signal if the item is selected, passing the
        given value as a parameter. Also updates the current value with the
        value of the selected item.
        '''
        self.emit('item-clicked', menu_item.get_label())

    def update_image(self):
        super(MenuButton, self).update_image()
        self.set_image(self._controller.get_current_image())

    def update_current_key(self):
        # select the item if it isn't already
        # item = self.get_menuitems()[self._controller.get_current_key_index()]

        # update the current image and tooltip
        self.set_image(self._controller.get_current_image())
        self.set_tooltip_text(self._controller.get_current_description())

    def do_button_press_event(self, event):
        '''
        when button is clicked, update the popup with the sorting options
        before displaying the popup
        '''
        if (event.button == Gdk.BUTTON_PRIMARY):
            self.show_popup()
            self.set_active(True)


class ImageToggleButton(PixbufButton, OptionsWidget):
    __gtype_name__ = "ImageToggleButton"

    def __init__(self, *args, **kwargs):
        '''
        Initializes the button.
        '''
        PixbufButton.__init__(self, *args, **kwargs)
        OptionsWidget.__init__(self, *args, **kwargs)

        # initialise some variables
        self.image_display = False
        self.initialised = False

    def update_image(self):
        super(ImageToggleButton, self).update_image()
        self.set_image(self._controller.get_current_image())


    def update_current_key(self):
        # update the current image and tooltip
        self.set_image(self._controller.get_current_image())
        self.set_tooltip_text(self._controller.get_current_description())

    def do_clicked(self):
        if self._controller:
            index = self._controller.get_current_key_index()
            index = (index + 1) % len(self._controller.options)

            # inform the controller
            self._controller.option_selected(
                self._controller.options[index])


class ImageRadioButton(Gtk.RadioButton, OptionsWidget):
    # this is legacy code that will not as yet work with
    # the new toolbar - consider removing this later

    __gtype_name__ = "ImageRadioButton"

    button_relief = GObject.property(type=bool, default=False)

    def __init__(self, *args, **kwargs):
        '''
        Initializes the button.
        '''
        Gtk.RadioButton.__init__(self, *args, **kwargs)
        OptionsWidget.__init__(self, *args, **kwargs)

        gs = GSetting()
        setting = gs.get_setting(gs.Path.PLUGIN)
        setting.bind(gs.PluginKey.BUTTON_RELIEF, self,
                     'button_relief', Gio.SettingsBindFlags.GET)

        self.connect('notify::button-relief',
                     self.on_notify_button_relief)

        # initialise some variables
        self.image_display = False
        self.initialised = False

        # ensure button appearance rather than standard radio toggle
        self.set_mode(False)

        #label colours
        self._not_active_colour = None
        self._active_colour = None

    def update_image(self):
        super(ImageRadioButton, self).update_image()
        # self.set_image(self._controller.get_current_image(Gtk.Buildable.get_name(self)))

    def do_toggled(self):
        if self.get_active():
            self.controller.option_selected(Gtk.Buildable.get_name(self))

    def set_image(self, pixbuf):
        image = self.get_image()

        if not image:
            image = Gtk.Image()
            super(ImageRadioButton, self).set_image(image)

        self.get_image().set_from_pixbuf(pixbuf)

        self.on_notify_button_relief()

    def on_notify_button_relief(self, *arg):
        if self.button_relief:
            self.set_relief(Gtk.ReliefStyle.NONE)
        else:
            self.set_relief(Gtk.ReliefStyle.HALF)

    def update_current_key(self):
        # update the current image and tooltip
        # self.set_image(self._controller.get_current_image(Gtk.Buildable.get_name(self)))
        self.set_tooltip_text("")  #self._controller.get_current_description())

        if self.controller.current_key == Gtk.Buildable.get_name(self):
            self.set_active(True)
            self._set_colour(Gtk.StateFlags.NORMAL)
        else:
            self._set_colour(Gtk.StateFlags.INSENSITIVE)

    def _set_colour(self, state_flag):

        if len(self.get_children()) == 0:
            return

        def get_standard_colour(label, state_flag):
            context = label.get_style_context()
            return context.get_color(state_flag)

        label0 = self.get_children()[0]

        if not self._not_active_colour:
            self._not_active_colour = get_standard_colour(label0, Gtk.StateFlags.INSENSITIVE)

        if not self._active_colour:
            self._active_colour = get_standard_colour(label0, Gtk.StateFlags.NORMAL)

        if state_flag == Gtk.StateFlags.INSENSITIVE:
            label0.override_color(Gtk.StateType.NORMAL, self._not_active_colour)
        else:
            label0.override_color(Gtk.StateType.NORMAL, self._active_colour)


class SearchEntry(RB.SearchEntry, OptionsPopupWidget):
    __gtype_name__ = "SearchEntry"

    # signals
    __gsignals__ = {
        'item-clicked': (GObject.SIGNAL_RUN_LAST, None, (str,))
    }

    def __init__(self, *args, **kwargs):
        RB.SearchEntry.__init__(self, *args, **kwargs)
        OptionsPopupWidget.__init__(self)
        # self.props.explicit_mode = True

    @OptionsPopupWidget.controller.setter
    def controller(self, controller):
        if self._controller:
            # disconnect signals
            self._controller.disconnect(self._search_text_changed_id)

        OptionsPopupWidget.controller.fset(self, controller)

        # connect signals
        self._search_text_changed_id = self._controller.connect(
            'notify::search-text', self._update_search_text)

        # update the current text
        self._update_search_text()

    def _update_search_text(self, *args):
        if not self.searching():
            self.grab_focus()
        self.set_text(self._controller.search_text)

    def update_current_key(self):
        super(SearchEntry, self).update_current_key()

        self.set_placeholder(self._controller.get_current_description())

    def do_show_popup(self):
        '''
        Callback called by the search entry when the magnifier is clicked.
        It prompts the user through a popup to select a filter type.
        '''
        self.show_popup(False)

    def do_search(self, text):
        '''
        Callback called by the search entry when a new search must
        be performed.
        '''
        if self._controller:
            self._controller.do_search(text)


class QuickSearchEntry(Gtk.Frame):
    __gtype_name__ = "QuickSearchEntry"

    # signals
    __gsignals__ = {
        'quick-search': (GObject.SIGNAL_RUN_LAST, None, (str,)),
        'arrow-pressed': (GObject.SIGNAL_RUN_LAST, None, (object,))
    }

    def __init__(self, *args, **kwargs):
        super(QuickSearchEntry, self).__init__(*args, **kwargs)
        self._idle = 0

        # text entry for the quick search input
        text_entry = Gtk.Entry(halign='center', valign='center',
                               margin=5)

        self.add(text_entry)

        self.connect_signals(text_entry)

    def get_text(self):
        return self.get_child().get_text()

    def set_text(self, text):
        self.get_child().set_text(text)

    def connect_signals(self, text_entry):
        text_entry.connect('changed', self._on_quick_search)
        text_entry.connect('focus-out-event', self._on_focus_lost)
        text_entry.connect('key-press-event', self._on_key_pressed)

    def _hide_quick_search(self):
        self.hide()

    def _add_hide_on_timeout(self):
        self._idle += 1

        def hide_on_timeout(*args):
            self._idle -= 1

            if not self._idle:
                self._hide_quick_search()

            return False

        Gdk.threads_add_timeout_seconds(GLib.PRIORITY_DEFAULT_IDLE, 4,
                                        hide_on_timeout, None)

    def do_parent_set(self, old_parent, *args):
        if old_parent:
            old_parent.disconnect(self._on_parent_key_press_id)

        parent = self.get_parent()
        self._on_parent_key_press_id = parent.connect('key-press-event',
                                                      self._on_parent_key_press, self.get_child())

    def _on_parent_key_press(self, parent, event, entry):
        if not self.get_visible() and \
                        event.keyval not in [Gdk.KEY_Shift_L,
                                             Gdk.KEY_Shift_R,
                                             Gdk.KEY_Control_L,
                                             Gdk.KEY_Control_R,
                                             Gdk.KEY_Escape,
                                             Gdk.KEY_Alt_L,
                                             Gdk.KEY_Super_L,
                                             Gdk.KEY_Super_R]:
            # grab focus, redirect the pressed key and make the quick search
            # entry visible
            entry.set_text('')
            entry.grab_focus()
            self.show_all()
            entry.im_context_filter_keypress(event)

        elif self.get_visible() and event.keyval == Gdk.KEY_Escape:
            self._hide_quick_search()

        return False

    def _on_quick_search(self, entry, *args):
        if entry.get_visible():
            # emit the quick-search signal
            search_text = entry.get_text()
            self.emit('quick-search', search_text)

            # add a timeout to hide the search entry
            self._add_hide_on_timeout()

    def _on_focus_lost(self, entry, *args):
        self._hide_quick_search()

        return False

    def _on_key_pressed(self, entry, event, *args):
        arrow = event.keyval in [Gdk.KEY_Up, Gdk.KEY_Down]

        if arrow:
            self.emit('arrow-pressed', event.keyval)
            self._add_hide_on_timeout()

        return arrow


class ProxyPopupButton(Gtk.Frame):
    __gtype_name__ = "ProxyPopupButton"

    def __init__(self, *args, **kwargs):
        super(ProxyPopupButton, self).__init__(*args, **kwargs)
        self._delegate = None

    @property
    def controller(self):
        if self._delegate:
            return self._delegate.controller

    @controller.setter
    def controller(self, controller):
        if self._delegate:
            self.remove(self._delegate)

        if len(controller.options) < 25:
            self._delegate = PopupButton()
        else:
            self._delegate = ListViewButton()

        self._delegate.set_visible(True)
        self._delegate.set_has_tooltip(True)
        self._delegate.set_can_focus(False)

        self._delegate.controller = controller
        self.add(self._delegate)


class OptionsListViewWidget(OptionsWidget):
    # signals
    __gsignals__ = {
        'item-clicked': (GObject.SIGNAL_RUN_LAST, None, (str,)),
        'deactivate': (GObject.SIGNAL_RUN_LAST, None, ())
    }

    def __init__(self, *args, **kwargs):
        OptionsWidget.__init__(self, *args, **kwargs)
        self._popup = self

    @OptionsWidget.controller.setter
    def controller(self, controller):
        ui = Gtk.Builder()
        ui.add_from_file(rb.find_plugin_file(controller.plugin,
                                             'ui/coverart_listwindow.ui'))
        ui.connect_signals(self)
        self._listwindow = ui.get_object('listwindow')
        self._liststore = ui.get_object('liststore')
        self._listwindow.set_size_request(200, 300)
        self._treeview = ui.get_object('treeview')
        self._scrollwindow = ui.get_object('scrolledwindow')
        self._scrolldown_button = ui.get_object('scrolldown_button')
        self._increment = False

        OptionsWidget.controller.fset(self, controller)

    def update_options(self):
        self.clear_options()
        self.add_options(self._controller.options)

    def update_current_key(self):
        self.select(self.controller.get_current_key_index())

    def do_item_clicked(self, key):
        if self._controller:
            # inform the controller
            self._controller.option_selected(key)

    def show_popup(self):
        '''
        show the listview window either above or below the controlling
        widget depending upon where the cursor position is relative to the
        screen
        params - x & y is the cursor position
        '''
        pos_x, pos_y = self.calc_popup_position(self._listwindow)

        self._listwindow.move(pos_x, pos_y)
        self._listwindow.show_all()

    def clear_options(self):
        self._liststore.clear()

    def add_options(self, iterable):
        for label in iterable:
            self._liststore.append((label,))

    def select(self, index):
        self._treeview.get_selection().select_iter(self._liststore[index].iter)
        self._treeview.scroll_to_cell(self._liststore[index].path)

    def on_button_click(self, view, arg):
        try:
            liststore, viewiter = view.get_selection().get_selected()
            label = liststore.get_value(viewiter, 0)
            self.emit('item-clicked', label)
        except:
            pass

        self._treeview.set_hover_selection(False)
        self._listwindow.hide()
        self.emit('deactivate')

    def on_scroll_button_enter(self, button):

        def scroll(*args):
            if self._increment:
                if button is self._scrolldown_button:
                    adjustment.set_value(adjustment.get_value()
                                         + self._step)
                else:
                    adjustment.set_value(adjustment.get_value()
                                         - self._step)

            return self._increment

        self._increment = True

        adjustment = self._scrollwindow.get_vadjustment()
        self.on_scroll_button_released()

        Gdk.threads_add_timeout(GLib.PRIORITY_DEFAULT_IDLE, 50,
                                scroll, None)

    def on_scroll_button_leave(self, *args):
        self._increment = False

    def on_scroll_button_pressed(self, *args):
        adjustment = self._scrollwindow.get_vadjustment()
        self._step = adjustment.get_page_increment()

    def on_scroll_button_released(self, *args):
        adjustment = self._scrollwindow.get_vadjustment()
        self._step = adjustment.get_step_increment()

    def on_treeview_enter_notify_event(self, *args):
        self._treeview.set_hover_selection(True)

    def on_cancel(self, *args):
        self._listwindow.hide()
        self.emit('deactivate')
        return True

    def do_delete_thyself(self):
        self.clear_list()
        del self._listwindow


class ListViewButton(PixbufButton, OptionsListViewWidget):
    __gtype_name__ = "ListViewButton"

    # signals
    __gsignals__ = {
        'item-clicked': (GObject.SIGNAL_RUN_LAST, None, (str,)),
        'deactivate': (GObject.SIGNAL_RUN_LAST, None, ())
    }

    def __init__(self, *args, **kwargs):
        '''
        Initializes the button.
        '''
        PixbufButton.__init__(self, *args, **kwargs)
        OptionsListViewWidget.__init__(self, *args, **kwargs)

        self._popup.connect('deactivate', self.popup_deactivate)

    def popup_deactivate(self, *args):
        # add a slight delay to allow the click of button to occur
        # before the deactivation of the button - this will allow
        # us to toggle the popup via the button correctly

        def deactivate(*args):
            self.set_active(False)

        Gdk.threads_add_timeout(GLib.PRIORITY_DEFAULT_IDLE, 50, deactivate, None)

    def update_image(self):
        super(ListViewButton, self).update_image()
        self.set_image(self._controller.get_current_image())

    def update_current_key(self):
        super(ListViewButton, self).update_current_key()

        # update the current image and tooltip
        self.set_image(self._controller.get_current_image())
        self.set_tooltip_text(self._controller.get_current_description())

    def do_button_press_event(self, event):
        '''
        when button is clicked, update the popup with the sorting options
        before displaying the popup
        '''
        if (event.button == Gdk.BUTTON_PRIMARY and not self.get_active()):
            self.show_popup()
            self.set_active(True)
        else:
            self.set_active(False)


class EnhancedIconView(Gtk.IconView):
    __gtype_name__ = "EnhancedIconView"

    # signals
    __gsignals__ = {
        'item-clicked': (GObject.SIGNAL_RUN_LAST, None, (object, object))
    }

    object_column = GObject.property(type=int, default=-1)

    def __init__(self, *args, **kwargs):
        super(EnhancedIconView, self).__init__(*args, **kwargs)

        self._reallocate_count = 0
        self.view_name = None
        self.source = None
        self.ext_menu_pos = 0

    def do_size_allocate(self, allocation):
        '''
        Forces the reallocation of the IconView columns when the width of the
        widgets changes. Neverthless, it takes into account that multiple
        reallocations could happen in a short amount of time, so it avoids
        trying to refresh until the user has stopped resizing the component.
        '''
        if self.get_allocated_width() != allocation.width:
            # don't need to reaccommodate if it's a vertical change
            self._reallocate_count += 1
            Gdk.threads_add_timeout(GLib.PRIORITY_DEFAULT_IDLE, 500,
                                    self._reallocate_columns, None)

        Gtk.IconView.do_size_allocate(self, allocation)

    def _reallocate_columns(self, *args):
        self._reallocate_count -= 1

        if not self._reallocate_count:
            self.set_columns(0)
            self.set_columns(-1)

    def do_button_press_event(self, event):
        '''
        Other than the default behavior, adds an event firing when the mouse
        has clicked on top of a current item, informing the listeners of the
        path of the clicked item.
        '''
        x = int(event.x)
        y = int(event.y)
        current_path = self.get_path_at_pos(x, y)

        if event.type is Gdk.EventType.BUTTON_PRESS and current_path:
            if event.triggers_context_menu():
                # if the item being clicked isn't selected, we should clear
                # the current selection
                if len(self.get_selected_objects()) > 0 and \
                        not self.path_is_selected(current_path):
                    self.unselect_all()

                self.select_path(current_path)
                self.set_cursor(current_path, None, False)

                if self.popup:
                    self.popup.popup(self.source, 'popup_menu', event.button, event.time)
            else:
                self.emit('item-clicked', event, current_path)

        Gtk.IconView.do_button_press_event(self, event)

    def get_selected_objects(self):
        '''
        Helper method that simplifies getting the objects stored on the
        selected items, givent that the object_column property is setted.
        This way there's no need for the client class to repeateadly access the
        correct column to retrieve the object from the raw rows.
        '''
        selected_items = self.get_selected_items()

        if not self.object_column:
            # if no object_column is setted, return the selected rows
            return selected_items

        model = self.get_model()
        selected_objects = list(reversed([model[selected][self.object_column]
                                          for selected in selected_items]))

        return selected_objects

    def select_and_scroll_to_path(self, path):
        '''
        Helper method to select and scroll to a given path on the IconView.
        '''
        self.unselect_all()
        self.select_path(path)
        self.set_cursor(path, None, False)
        self.scroll_to_path(path, True, 0.5, 0.5)


class HiddenExpander(Gtk.Bin):
    __gtype_name__ = "HiddenExpander"

    expanded = GObject.property(type=bool, default=False)
    label = GObject.property(type=str, default='')

    def __init__(self, label='', visible=False):
        super(HiddenExpander, self).__init__()  # *args, **kwargs)
        self.label = label
        self.set_visible(visible)

    def get_expanded(self):
        return self.expanded

    def set_expanded(self, expanded):
        self.expanded = expanded


class PanedCollapsible(Gtk.Paned):
    __gtype_name__ = "PanedCollapsible"

    # properties
    # this two properties indicate which one of the Paned childs is collapsible
    # only one can be True at a time, the widget takes care of keeping this
    # restriction consistent.
    collapsible1 = GObject.property(type=bool, default=False)
    collapsible2 = GObject.property(type=bool, default=False)

    # values for expand method
    Paned = enum(DEFAULT=1, EXPAND=2, COLLAPSE=3)

    # this indicates the latest position for the handle before a child was
    # collapsed
    collapsible_y = GObject.property(type=int, default=0)

    # label for the Expander used on the collapsible child
    collapsible_label = GObject.property(type=str, default='')

    # signals
    __gsignals__ = {
        'expanded': (GObject.SIGNAL_RUN_LAST, None, (bool,))
    }

    Min_Paned_Size = 80

    def __init__(self, *args, **kwargs):
        super(PanedCollapsible, self).__init__(*args, **kwargs)
        self._connect_properties()
        self._from_paned_handle = 0

    def _connect_properties(self):
        self.connect('notify::collapsible1', self._on_collapsible1_changed)
        self.connect('notify::collapsible2', self._on_collapsible2_changed)
        self.connect('notify::collapsible_label',
                     self._on_collapsible_label_changed)

    def _on_collapsible1_changed(self, *args):
        if self.collapsible1 and self.collapsible2:
            # check consistency, only one collapsible at a time
            self.collapsible2 = False

        child = self.get_child1()

        self._wrap_unwrap_child(child, self.collapsible1, self.add1)

    def _on_collapsible2_changed(self, *args):
        if self.collapsible1 and self.collapsible2:
            # check consistency, only one collapsible at a time
            self.collapsible1 = False

        child = self.get_child2()

        self._wrap_unwrap_child(child, self.collapsible2, self.add2)

    def _wrap_unwrap_child(self, child, wrap, add):
        if child:
            self.remove(child)

            if not wrap:
                inner_child = child.get_child()
                child.remove(inner_child)
                child = inner_child

            add(child)

    def _on_collapsible_label_changed(self, *args):
        if self._expander:
            self._expander.set_label(self.collapsible_label)

    def _on_collapsible_expanded(self, *args):
        expand = self._expander.get_expanded()

        if not expand:
            self.collapsible_y = self.get_position()

            # move the lower pane to the bottom since it's collapsed
            self._collapse()
        else:
            # reinstate the lower pane to it's expanded size
            if not self.collapsible_y:
                # if there isn't a saved size, use half of the space
                new_y = self.get_allocated_height() / 2
                self.collapsible_y = new_y

            # if the calculated new position is less than the minimum then
            # use half the space

            current_pos = self.get_allocated_height() - \
                          self.get_handle_window().get_height()

            if ((current_pos - self.collapsible_y) < self.Min_Paned_Size):
                self.collapsible_y = self.get_allocated_height() / 2

            self.set_position(self.collapsible_y)

        self.emit('expanded', expand)

    def do_button_press_event(self, event):
        '''
        This callback allows or denies the paned handle to move depending on
        the expanded expander
        '''
        # if not self._expander or self._expander.get_expanded():
        self._from_paned_handle = 1

        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self._from_paned_handle = 2

        Gtk.Paned.do_button_press_event(self, event)

    def do_button_release_event(self, *args):
        '''
        Callback when the paned handle is released from its mouse click.
        '''
        if self._from_paned_handle != 0:
            Gtk.Paned.do_button_release_event(self, *args)

        if (not self._expander or self._expander.get_expanded()) and self._from_paned_handle == 1:
            print("in an expanded situation")
            self.collapsible_y = self.get_position()

            # if the current paned handle pos is less than the minimum the force a collapse
            current_pos = self.get_allocated_height() - \
                          self.get_handle_window().get_height()

            if ((current_pos - self.collapsible_y) < self.Min_Paned_Size):
                self.expand(PanedCollapsible.Paned.COLLAPSE)

        # if self._from_paned_handle == 2: 
        #     # we are dealing with a double click situation

        # to do: collapse/expand depending on pref (CoverLocale singleton)
        #        By now, I prevent from changes by commenting all the logic
        #     if self._expander.get_expanded():
        #         # if we are in an expanded position - lets collapse the pane
        #         print("collapsing")
        #         self.expand(PanedCollapsible.Paned.COLLAPSE)
        #     else:
        #         # the current paned position is closed, so lets open the pane fully
        #         self.expand(PanedCollapsible.Paned.EXPAND)
        #         print("expanding")
        #         self.set_position(0)
        self._from_paned_handle = 0

    def do_remove(self, widget):
        '''
        Overwrites the super class remove method, taking care of removing the
        child even if it's wrapped inside an Expander.
        '''
        if self.collapsible1 and self.get_child1().get_child() is widget:
            expander = self.get_child1()
            expander.remove(widget)
            widget = expander
        elif self.collapsible2 and self.get_child2().get_child() is widget:
            expander = self.get_child2()
            expander.remove(widget)
            widget = expander

        self._expander = None

        Gtk.Paned.remove(self, widget)

    def do_add(self, widget):
        '''
        This method had to be overridden to allow the add and packs method to
        work with Glade.
        '''
        if not self.get_child1():
            self.do_add1(widget)
        elif not self.get_child2():
            self.do_add2(widget)
        else:
            print("GtkPaned cannot have more than 2 children")

    def do_add1(self, widget):
        '''
        Overrides the add1 superclass' method for pack1 to work correctly.
        '''
        self.do_pack1(widget, True, True)

    def do_pack1(self, widget, *args, **kwargs):
        '''
        Packs the widget into the first paned child, adding a GtkExpander
        around the packed widget if the collapsible1 property is True.
        '''
        if self.collapsible1:
            widget = self._create_expander(widget)

        Gtk.Paned.pack1(self, widget, *args, **kwargs)

    def do_add2(self, widget):
        '''
        Overrides the add2 superclass' method for pack2 to work correctly.
        '''
        self.do_pack2(widget, True, True)

    def do_pack2(self, widget, *args, **kwargs):
        '''
        Packs the widget into the second paned child, adding a GtkExpander
        around the packed widget if the collapsible2 property is True.
        '''
        if self.collapsible2:
            widget = self._create_expander(widget)

        Gtk.Paned.pack2(self, widget, *args, **kwargs)

    def _create_expander(self, widget):
        # self._expander = Gtk.Expander(label=self.collapsible_label,
        #                              visible=True)
        self._expander = HiddenExpander(label=self.collapsible_label,
                                        visible=True)

        self._expander.add(widget)

        # connect the expanded signal
        self._expander.connect('notify::expanded',
                               self._on_collapsible_expanded)

        ## Removed initial collapse
        # connect the initial collapse
        # self._allocate_id = self._expander.connect('size-allocate',
        #                                            self._initial_collapse)

        return self._expander

    def _initial_collapse(self, *args):
        self._collapse()
        self._expander.disconnect(self._allocate_id)
        del self._allocate_id

    def _collapse(self):
        new_y = self.get_allocated_height() - \
                self.get_handle_window().get_height()  # - \
        # self._expander.get_label_widget().get_allocated_height()

        self.set_position(new_y)

    def expand(self, force):
        '''
        Toggles the expanded property of the collapsible children.
        unless requested to force expansion
        '''
        if self._expander:
            if force == PanedCollapsible.Paned.EXPAND:
                self._expander.set_expanded(True)
            elif force == PanedCollapsible.Paned.COLLAPSE:
                self._expander.set_expanded(False)
            elif force == PanedCollapsible.Paned.DEFAULT:
                self._expander.set_expanded(not self._expander.get_expanded())

    def get_expansion_status(self):
        '''
        returns the position of the expander i.e. expanded or not
        '''
        value = PanedCollapsible.Paned.COLLAPSE
        if self._expander and self._expander.get_expanded():
            value = PanedCollapsible.Paned.EXPAND

        return value


class AbstractView(GObject.Object):
    '''
    intention is to document 'the must have' methods all views should define
    N.B. this is preliminary and will change as and when
    coverflow view is added with lessons learned
    '''
    view = None
    panedposition = PanedCollapsible.Paned.DEFAULT
    use_plugin_window = True
    # signals - note - pygobject doesnt appear to support signal declaration
    # in multiple inheritance - so these signals need to be defined in all view classes
    # where abstractview is part of multiple inheritance
    __gsignals__ = {
        'update-toolbar': (GObject.SIGNAL_RUN_LAST, None, ())
    }

    def __init__(self):
        super(AbstractView, self).__init__()

    def initialise(self, source):
        self.source = source
        self.plugin = source.plugin

        self._notification_displayed = 0
        Notify.init("coverart_browser")

        self.connect('update-toolbar', self.do_update_toolbar)

    def do_update_toolbar(self, *args):
        '''
            called when update-toolbar signal is emitted
            by default the toolbar objects are made visible
        '''
        from coverart_toolbar import ToolbarObject

        self.source.toolbar_manager.set_enabled(True, ToolbarObject.SORT_BY)
        self.source.toolbar_manager.set_enabled(True, ToolbarObject.SORT_ORDER)
        self.source.toolbar_manager.set_enabled(False, ToolbarObject.SORT_BY_ARTIST)
        self.source.toolbar_manager.set_enabled(False, ToolbarObject.SORT_ORDER_ARTIST)

    def display_notification(self, title, text, file):

        # first see if the notification plugin is enabled
        # if it is, we use standard notifications
        # if it is not, we use the infobar

        def hide_notification(*args):
            if self._notification_displayed > 7:
                self.source.notification_infobar.response(0)
                self._notification_displayed = 0
                return False

            self._notification_displayed = self._notification_displayed + 1
            return True

        notifyext = ExternalPlugin()
        notifyext.appendattribute('plugin_name', 'notification')

        if notifyext.is_activated():
            n = Notify.Notification.new(title, text, file)
            n.show()
        else:
            self.source.notification_text.set_text(title + " : " + text)
            # self.source.notification_infobar.set_visible(True)#reveal_notification.set_reveal_child(True)
            self.source.notification_infobar.show()  #reveal_notification.set_reveal_child(True)

            if self._notification_displayed == 0:
                Gdk.threads_add_timeout_seconds(GLib.PRIORITY_DEFAULT_IDLE, 1,
                                                hide_notification, None)
            else:
                self._notification_displayed = 1  # reset notification for new label


    def resize_icon(self, cover_size):
        '''
        resize the view main picture icon

        :param cover_size: `int` icon size
        '''
        pass

    def get_selected_objects(self):
        '''
        finds what has been selected

        returns an array of `Album`
        '''
        pass

    def selectionchanged_callback(self, *args):
        '''
        callback when a selection has changed
        '''
        self.source.update_with_selection()

    def select_and_scroll_to_path(self, path):
        '''
        find a path and highlight (select) that object
        '''
        pass

    def scroll_to_album(self, album):
        '''
        scroll to the album in the view
        '''
        if album:
            path = self.source.album_manager.model.get_path(album)
            if path:
                self.select_and_scroll_to_path(path)

    def set_popup_menu(self, popup):
        '''
        define the popup menu (right click) used for the view
        '''
        self.popup = popup

    def grab_focus(self):
        '''
        ensures main view object retains the focus
        '''
        pass

    def switch_to_view(self, source, album):
        '''
        ensures that when the user toggles to a view stuff remains
        consistent
        '''
        pass

    def get_view_icon_name(self):
        '''
        every view should have an icon - subject to removal
        since we'll probably just have text buttons for the view
        '''
        return ""

    def get_default_manager(self):
        '''
        every view should have a default manager
        for example an AlbumManager or ArtistManager
        by default - use the AlbumManager from the source
        '''

        return self.source.album_manager

    def switch_to_coverpane(self, cover_search_pane):
        '''
        called from the source to update the coverpane when
        it is switched from the track pane
        '''

        selected = self.get_selected_objects()

        if selected:
            manager = self.get_default_manager()
            cover_search_pane.do_search(selected[0],
                                        manager.cover_man.update_cover)

