#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, shelve
from os import path
import time
import gtk, pygtk, pango
from gimpfu import *
import gimpui
from gtkcodebuffer import CodeBuffer, SyntaxLoader, add_syntax_path
from ConfigParser import ConfigParser
import xml.etree.ElementTree as ET

# test:
from pdb import set_trace

PAR_TYPES = ('INT32',
            'INT18',
            'INT8',
            'FLOAT',
            'STRING',
            'INT32ARRAY',
            'INT16ARRAY',
            'INT8ARRAY',
            'FLOATARRAY',
            'STRINGARRAY',
            'COLOR',
            'ITEM',
            'DISRLAY',
            'IMAGE',
            'LAYER',
            'CHANNEL',
            'DRAWABLE',
            'SELECTION',
            'VECTORS')

ST_SAVED = _('Saved')
ST_EDITED = _('Edited')
ST_NEW = _('New')


# self._ckey - current fragment key
class BatchCodeExec:
       
    def __init__(self):
        _path = path.dirname(sys.modules[self.__module__].__file__)

        _conf_filename = '%s/config' %_path
        _conf_dict = {
            'Menu': {'Layer': 'gimp-layer*'},
            'Templates': {'Get first layer': 'layer = image.layers[0]'}
            }
        if not(path.isfile(_conf_filename)):
            self._create_conf_file(_conf_filename, _conf_dict)
        self.config = ConfigParser()
        self.config.read(_conf_filename) 
        self._check_conf(_conf_filename, _conf_dict)       

        self.ui = gtk.Builder()
        self.ui.set_translation_domain('GEB')
        self.ui.add_from_file('%s/batch_ex.ui' %_path)
        self.ui.connect_signals(self)
        self.status = self.ui.get_object('status')

        #Check Gimp version and updade syntax file, if needed
        self._check_syntax('%s/python-fu.xml' %_path)

        add_syntax_path(_path)
        buff = CodeBuffer(lang=SyntaxLoader("python-fu"))
        self.ui.get_object('code').set_buffer(buff)
        buff.connect('changed', self.code_changed)

        self.base = shelve.open('%s/batch_base' %_path)
        self._get_macro_list()
        self._ckey = ""
        self.browse_dlg = None

        # Menu
        self._create_menu()

        # colors
        self.red_color = pango.AttrList()
        self.red_color.insert(pango.AttrForeground(65535, 0, 0, 0, -1))
        self.red_color.insert(pango.AttrWeight(pango.WEIGHT_HEAVY, 0, -1))
        self.green_color = pango.AttrList()
        self.green_color.insert(pango.AttrForeground(0, 65535, 0, 0, -1))        
        self.green_color.insert(pango.AttrWeight(pango.WEIGHT_HEAVY, 0, -1))
        self.blue_color = pango.AttrList()
        self.blue_color.insert(pango.AttrForeground(0, 0, 65535, 0, -1)) 
        self.blue_color.insert(pango.AttrWeight(pango.WEIGHT_HEAVY, 0, -1))

        # Log
        self._log = self.ui.get_object('log').get_buffer()
        self._log.create_tag('alert', foreground='red', weight=700)
        self._log.create_tag('ok', foreground='black')
        self._log.create_tag('done', foreground='blue', weight=700)

        self._set_status(ST_NEW)
        self.format_changed(self.ui.get_object('format_combo'))
        self._add_log(_('GEB started!'), 'done')

    # Add to log
    def _add_log(self, message, tag='ok'):
        timestring = time.strftime('%d.%m.%Y %H:%M:%S ', time.localtime())
        self._log.insert_with_tags_by_name(self._log.get_end_iter(),
            timestring + message + '\n', tag)

    # Check Gimp version and updade syntax file, if needed
    def _check_syntax(self, filename):
        def indent(elem, level=0):
            i = "\n" + level*"  "
            if len(elem):
                if not elem.text or not elem.text.strip():
                    elem.text = i + "  "
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i
                for elem in elem:
                    indent(elem, level+1)
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i
            else:
                if level and (not elem.tail or not elem.tail.strip()):
                    elem.tail = i        
        syn_parser = ET.ElementTree()
        syn_parser.parse(filename)
        gimp_version = syn_parser.find('gimp-version')
        if gimp_version.text == str(gimp.version):
            return
        gimp_version.text = str(gimp.version)
        funclist = syn_parser.find("keywordlist[@style='function']")
        funclist.clear()
        funclist.attrib['style'] = 'function'
        for key in pdb.query():
            func_element = ET.Element('keyword')          
            func_element.text = 'pdb.%s' %key.replace('-', '_')
            funclist.append(func_element)
        for top_elem in syn_parser.findall('.'): indent(top_elem)
        syn_parser.write(filename)        

    # Create config file
    def _create_conf_file(self, filename, conf_dict):
        config = ConfigParser()
        sections = conf_dict.keys()
        sections.sort()
        for section in sections:
            config.add_section(section)
            for option in conf_dict[section]:
                config.set(section, option, conf_dict[section][option])
        config.write(open(filename,'w'))     

    # Check and fix config
    def _check_conf(self, filename, conf_dict):
        sections = conf_dict.keys()
        sections.sort()
        for section in sections:
            if section not in self.config.sections():
                self.config.add_section(section)
                for option in conf_dict[section]:
                    self.config.set(section, option, conf_dict[section][option])
        self.config.write(open(filename,'w'))            
  
    # Editor menu
    def _create_menu(self):
        menu = self.ui.get_object('code_menu')

        # PDB function menu
        pdb_menuitem = gtk.MenuItem('PDB')
        pdb_menu = gtk.Menu()
        browser_item = gtk.MenuItem(_("PDB Browser"))
        browser_item.connect('activate', self.show_browser)
        pdb_menu.add(browser_item)
        browser_item.show()
        pdb_menuitem.set_submenu(pdb_menu)
        menu.add(pdb_menuitem)
        pdb_menuitem.show()

        # Templates menu
        template_menuitem = gtk.MenuItem('Templates')
        template_menu = gtk.Menu()
        for item in self.config.options('Templates'):           
            submenu_item = gtk.MenuItem(item)
            submenu_item.connect('activate', self.add_code,
                self.config.get('Templates', item)) 
            template_menu.append(submenu_item)
            submenu_item.show()               
        template_menuitem.set_submenu(template_menu)
        menu.add(template_menuitem)
        template_menuitem.show() 

        # Settings menu
        settings_menuitem = gtk.MenuItem('Settings')
        settings_menu = gtk.Menu()

        # PDB function arguments
        self.args = gtk.CheckMenuItem('PDB arguments')
        settings_menu.append(self.args)
        self.args.show()      

        settings_menuitem.set_submenu(settings_menu)
        menu.add(settings_menuitem)
        settings_menuitem.show()                

    # Editor status change
    def _set_status(self, status):
        if status == ST_NEW:
            self.status.set_attributes(self.blue_color);
        elif status == ST_SAVED:
            self.status.set_attributes(self.green_color);
        elif status == ST_EDITED:
            self.status.set_attributes(self.blue_color);
        else:
            return
        self.status.set_text(status)

    # Alert message
    def _alert(self, mtext):
        em = gtk.MessageDialog(self.ui.get_object('root_window'), 
            gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, 
            gtk.BUTTONS_CLOSE, str(mtext))
        em.run()
        em.destroy() 

    # Get code (self.code)
    def _get_code(self):
        code_buffer = self.ui.get_object('code').get_buffer()
        self.code = code_buffer.get_text(code_buffer.get_start_iter(),
            code_buffer.get_end_iter())     

    #Code execution (use variable "image")
    def _ex_code(self, image):
        try:
            exec(self.code)
        except Exception, error:
            self._add_log(_('Code error: ')+str(error), 'alert')
            self._alert(str(error))
            return False
        return True

    #File save
    def _save_img(self, img):
        format = self.ui.get_object('format_combo').get_active()        
        if (format != 2) and (img.layers.__len__() > 1):
            pdb.gimp_image_flatten(img)
        layer = img.layers[0]
        root_filename = path.splitext(path.basename(img.filename))[0]
        filename = path.join(
            self.ui.get_object('dir_select').get_filename(),
            path.splitext(path.basename(img.filename))[0] \
            + ('.jpg', '.tif', '.xcf', '.bmp')[format])
        #JPG
        if format == 0:
            compress = self.ui.get_object('hscale1').get_value()
            pdb.file_jpeg_save(img, layer, filename, filename, compress,
                0, 0, 0, "GEB", 1, 0, 0, 2)
        #TIFF
        elif format == 1:
            compress = int(self.ui.get_object('checkbutton1').get_active())
            pdb.file_tiff_save(img, layer, filename, filename, compress)
        #XCF
        elif format == 2:
            pdb.gimp_xcf_save(0, img, layer, filename, filename)
        elif format == 3:
            pdb.file_bmp_save(img, layer, filename, filename)

    # Fill fragments list
    def _get_macro_list(self):
        macro_list = self.ui.get_object('liststore1')
        macro_list.clear()
        for key in sorted(self.base.keys()):
            list_iter = macro_list.append(None)
            macro_list[list_iter] = (key, self.base[key]['descr'])

    # Reset editor and current fragment
    def _clear_editor(self):
        self._ckey = ''
        self.ui.get_object('entry_descr').set_text('')
        self.ui.get_object('code').get_buffer().set_text('')
        self._set_status(ST_NEW)

    # Key generator
    def _keygen(self):
        if self.base.keys():
            return '%05d' %(int(sorted(self.base.keys())[-1])+1)
        else:
            return '00000'

    # Get PDB procedure with user arguments
    def get_pdb_args(self, proc, params):
        proc_cmd = ''
        if len(proc.return_vals) > 0:
            proc_cmd = ', '.join([x[1].replace('-', '_')
                                 for x in proc.return_vals]) + ' = '
        proc_name = proc.proc_name.replace('-', '_')
        proc_cmd = proc_cmd + 'pdb.%s' % proc_name

        if params.__len__() == 0:
            return proc_cmd

        dialog = gtk.Dialog(proc_name, self.browse_dlg, 0,
                            (gtk.STOCK_OK, gtk.RESPONSE_OK,
                             gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))

        table = gtk.Table(params.__len__(), 2)
        table.set_row_spacings(4)
        table.set_col_spacings(4)
        dialog.vbox.pack_start(table, True, True, 0)
        t_row = 0
        entrs = []

        for param in params:
            label = gtk.Label(str(param[1]))
            table.attach(label, 0, 1, t_row, t_row+1)
            entr = gtk.Entry()
            entr.set_text(str(param[1]))
            entr.set_tooltip_markup('<b>%s</b>\n<i>%s</i>\n%s'\
                                    %(param[1], PAR_TYPES[param[0]], param[2]))
            table.attach(entr, 1, 2, t_row, t_row+1)
            label.set_mnemonic_widget(entr)
            t_row += 1
            entrs.append(entr)

        dialog.show_all()
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            proc_cmd += '(%s)' % ', '.join([x.get_text().replace('-', '_')
                                           for x in entrs])
        else:
            proc_cmd = ''
        dialog.destroy()
        return proc_cmd

    # PDB Browser response
    def browse_response(self, dlg, response_id):
        if response_id != gtk.RESPONSE_APPLY:
            dlg.hide()
            return
        proc_name = dlg.get_selected()

        if not proc_name:
            return
        proc = pdb[proc_name]
        if proc.params.__len__() > 0 and proc.params[0][1] == 'run-mode':
            params = proc.params[1:]
        else:
            params = proc.params        
        cmd = ''

        if self.args.get_active():
            cmd = cmd + self.get_pdb_args(proc, params)
        else:
            if len(proc.return_vals) > 0:
                cmd = ', '.join([x[1].replace('-', '_')
                                for x in proc.return_vals]) + ' = '
            cmd = cmd + 'pdb.%s' % proc.proc_name.replace('-', '_')
            cmd = cmd + '(%s)' % ', '.join([x[1].replace('-', '_')
                                           for x in params])
        self.add_code(None, cmd)
        self.ui.get_object('root_window').present()
        self.ui.get_object('code').grab_focus()

    def show_browser(self, widget):
        if not self.browse_dlg:
            dlg = gimpui.ProcBrowserDialog(_("Python Procedure Browser"),
                                           role='gimp_exec_batch',
                                           buttons=(gtk.STOCK_APPLY,
                                                    gtk.RESPONSE_APPLY,
                                                    gtk.STOCK_CLOSE,
                                                    gtk.RESPONSE_CLOSE))
            dlg.set_default_response(gtk.RESPONSE_APPLY)
            dlg.set_alternative_button_order((gtk.RESPONSE_CLOSE,
                                              gtk.RESPONSE_APPLY))
            dlg.connect('response', self.browse_response)
            dlg.connect('row-activated',
                        lambda dlg: dlg.response(gtk.RESPONSE_APPLY))
            self.browse_dlg = dlg

        self.browse_dlg.present() 

    # Hide PDB Brower
    def hide_browser(self, widget, event):
        widget.hide()
        return True                  

    # Code insert
    def add_code(self, widget, insert_code):
        code_buffer = self.ui.get_object('code').get_buffer()
        code_buffer.insert_at_cursor(insert_code)

    # Clear file fils
    def clear_filelist(self, widget):
        self.ui.get_object('liststore4').clear()

    # Add files to filelist
    def run_chooser(self, widget):
        add_dialog = gtk.FileChooserDialog(_("Add files..."), None,
            gtk.FILE_CHOOSER_ACTION_OPEN,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        add_dialog.set_default_response(gtk.RESPONSE_OK)
        add_dialog.set_select_multiple(True)

        filter = gtk.FileFilter()
        filter.set_name(_("All files"))
        filter.add_pattern("*")
        add_dialog.add_filter(filter)

        filter = gtk.FileFilter()
        filter.set_name(_("Images"))
        filter.add_mime_type("image/png")
        filter.add_mime_type("image/jpeg")
        filter.add_mime_type("image/gif")
        filter.add_pattern("*.[pP][nN][gG]")
        filter.add_pattern("*.[jJ][pP][gG]")
        filter.add_pattern("*.[gG][iI][fF]")
        filter.add_pattern("*.[tT][iI][fF]")
        filter.add_pattern("*.[xX][pP][mM]")
        add_dialog.add_filter(filter) 
        add_dialog.set_filter(filter) 

        response = add_dialog.run()
        if response == gtk.RESPONSE_OK:
            add_files = add_dialog.get_filenames()
            file_store = self.ui.get_object('liststore4')
            file_list = (x[0] for x in file_store)
            for filename in add_files:
                if filename not in file_list:
                    list_iter = file_store.append(None)
                    file_store[list_iter] = (filename, )          
        add_dialog.destroy()

    # Change code in editor
    def code_changed(self, widget):
        if self.status.get_text() == ST_SAVED:
            self._set_status(ST_EDITED)

    # key press (Enter, Save etc)
    def key_press(self, widget, event):
        if widget == self.ui.get_object('entry_descr')\
        and gtk.gdk.keyval_name(event.keyval) == 'Return':
            self.ui.get_object('code').grab_focus()
        elif (event.state & gtk.gdk.CONTROL_MASK)\
        and gtk.gdk.keyval_name(event.keyval) == 's':
            self.code_save(widget)

    # New fragment
    def create_fragment(self, widget):
        self._clear_editor()
        self.ui.get_object('notebook1').set_current_page(2)   

    # Next page  
    def click_forward(self, widget): 
        self.ui.get_object('notebook1').next_page()

    # Save edited code
    def code_save(self, widget):
        descr = self.ui.get_object('entry_descr').get_text()
        if descr == '':
            self._alert(_('Enter title!'))
            return
        if self._ckey == '': self._ckey = self._keygen()        
        code_buffer = self.ui.get_object('code').get_buffer()
        code = code_buffer.get_text(
            code_buffer.get_start_iter(), code_buffer.get_end_iter())
        self._set_status(ST_SAVED)
        self._add_log(_('Code saved'), 'done')
        self.base[self._ckey] = {'descr':descr, 'code':code}
        self.base.sync()
        self._get_macro_list()

    # Select format
    def format_changed(self, widget):
        self.ui.get_object('notebook2').set_current_page(widget.get_active()+1)

    # Select code fragment
    def select_fragment(self, widget, tree_path, column):
        self._ckey = widget.get_model()[tree_path][0]
        self.ui.get_object('entry_descr').set_text(
            self.base[self._ckey]['descr'])
        self.ui.get_object('code').\
            get_buffer().set_text(self.base[self._ckey]['code'])
        self.ui.get_object('notebook1').set_current_page(2) 
        self._set_status(ST_SAVED)

    # Delete fragment
    def delete_fragment(self, widget):
        macro_list, sel_iter =\
            self.ui.get_object('treeview1').get_selection().get_selected()
        key = macro_list[sel_iter][0]
        del self.base[key]
        self.base.sync()
        self._get_macro_list()
        if key == self._ckey: self._clear_editor()

    # Execution code for selected images
    def do_selected(self, widget):
        self._get_code()
        filenames = [x[0] for x in self.ui.get_object('liststore4')]
        self.ui.get_object('notebook2').set_current_page(0)  
        file_count = filenames.__len__()
        file_num = err_count = done_count = 0    
        for filename in filenames:
            file_num += 1
            self.ui.get_object('progress').set_fraction(
                float(file_num)/float(file_count))
            self.ui.get_object('current_file').set_text('%s (%s/%s)'\
                %(filename, str(file_num), str(file_count)))
            while gtk.events_pending():
               gtk.main_iteration(False)  
            try:
                image = pdb.gimp_file_load(filename, filename)
            except Exception, error:
                self._add_log(_('File error: ') + str(error), 'alert')
                err_count += 1
                continue                     
            if not self._ex_code(image):
                pdb.gimp_image_delete(image) 
                break   
            self._save_img(image)
            pdb.gimp_image_delete(image) 
            done_count += 1
        self._add_log(_('Files selected: ') + str(file_count))
        self._add_log(_('Files processed: ') + str(done_count), 'done') 
        self._add_log(_('File errors: ') + str(err_count),
            'alert' if err_count else 'done') 
        self.format_changed(self.ui.get_object('format_combo'))
        self.ui.get_object('notebook1').set_current_page(4)

    # Execution code for opened images
    def do_opened(self, widget):
        self._get_code()
        image_list = gimp.image_list()
        self.ui.get_object('notebook2').set_current_page(0) 
        count = image_list.__len__()
        num = 0
        for image in image_list:
            self.ui.get_object('progress').set_fraction(
                float(num)/float(count))
            self.ui.get_object('current_file').set_text('%s (%s/%s)'\
                %(path.basename(image.filename), str(num), str(count)))
            while gtk.events_pending():
               gtk.main_iteration(False)  
            pdb.gimp_image_undo_group_start(image)
            if not self._ex_code(image):
                pdb.gimp_image_undo_group_end(image)
                break               
            pdb.gimp_image_undo_group_end(image)
        self.format_changed(self.ui.get_object('format_combo'))

    # Close app
    def close_app(self, widget):
        self.base.close()
        gtk.main_quit()
