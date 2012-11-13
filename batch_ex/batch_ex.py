#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, shelve
from os import path
import pygtk
import gtk
from gimpfu import *
import gimpui
from gtkcodebuffer import CodeBuffer, SyntaxLoader, add_syntax_path
import pango
from ConfigParser import ConfigParser

t = gettext.translation('gimp20-python', gimp.locale_directory, fallback=True)
_ = t.ugettext

# test:
from pdb import set_trace


# self._ckey - ключ текущего фрагмента
class BatchCodeExec:
       
    def __init__(self):
        _path = path.dirname(sys.modules[self.__module__].__file__)

        _conf_filename = _path + '/config'
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
        self.ui.add_from_file(_path+'/batch_ex.ui')
        self.ui.connect_signals(self)
        self.status = self.ui.get_object('status')

        add_syntax_path(_path)
        buff = CodeBuffer(lang=SyntaxLoader("python"))
        self.ui.get_object('code').set_buffer(buff)
        buff.connect('changed', self.code_changed)

        self.base = shelve.open(_path+'/batch_base')
        self._get_macro_list()
        self._ckey = ""
        self.browse_dlg = None
        #Menu
        self._create_menu()

        #colors
        self.red_color = pango.AttrList()
        self.red_color.insert(pango.AttrForeground(65535, 0, 0, 0, -1))
        self.red_color.insert(pango.AttrWeight(pango.WEIGHT_HEAVY, 0, -1))
        self.green_color = pango.AttrList()
        self.green_color.insert(pango.AttrForeground(0, 65535, 0, 0, -1))        
        self.green_color.insert(pango.AttrWeight(pango.WEIGHT_HEAVY, 0, -1))
        self.blue_color = pango.AttrList()
        self.blue_color.insert(pango.AttrForeground(0, 0, 65535, 0, -1)) 
        self.blue_color.insert(pango.AttrWeight(pango.WEIGHT_HEAVY, 0, -1))

        self._set_status("New")

    #Create config file
    def _create_conf_file(self, filename, conf_dict):
        config = ConfigParser()
        sections = conf_dict.keys()
        sections.sort()
        for section in sections:
            config.add_section(section)
            for option in conf_dict[section]:
                config.set(section, option, conf_dict[section][option])
        config.write(open(filename,'w'))     

    #Check and fix config
    def _check_conf(self, filename, conf_dict):
        sections = conf_dict.keys()
        sections.sort()
        for section in sections:
            if section not in self.config.sections():
                self.config.add_section(section)
                for option in conf_dict[section]:
                    self.config.set(section, option, conf_dict[section][option])
        self.config.write(open(filename,'w'))            
  
    #Меню редактора
    def _create_menu(self):
        menu = self.ui.get_object('code_menu')

        #Меню функций PDB
        pdb_menuitem = gtk.MenuItem('PDB')
        pdb_menu = gtk.Menu()
        browser_item = gtk.MenuItem("Browser")
        browser_item.connect('activate', self.show_browser)
        pdb_menu.add(browser_item)
        browser_item.show()
        for item in self.config.options('Menu'):           
            menuitem = gtk.MenuItem(item)
            submenu = gtk.Menu()
            pdb_list = pdb.query(self.config.get('Menu', item))
            pdb_list.sort()
            for pdb_item in pdb_list:
                pdb_proc = pdb[pdb_item]
                submenu_item = gtk.MenuItem(pdb_item)
                submenu_item.set_tooltip_markup(
                    '<b>' + pdb_proc.proc_blurb + '</b>\n'\
                    + pdb_proc.proc_help)
                submenu.append(submenu_item)
                submenu_item.connect('activate', self.add_code, pdb_item +\
                    '(' + reduce(lambda res,x: res+x[1]+', ',\
                    pdb_proc.params, '')[:-2] + ')')
                submenu_item.show()
            menuitem.set_submenu(submenu)
            pdb_menu.add(menuitem)
            menuitem.show()
        pdb_menuitem.set_submenu(pdb_menu)
        menu.add(pdb_menuitem)
        pdb_menuitem.show()

        #Меню шаблонов
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

    #Изменение статуса редактора
    def _set_status(self, status):
        if status == 'New':
            self.status.set_attributes(self.blue_color);
        elif status == 'Saved':
            self.status.set_attributes(self.green_color);
        elif status == 'Edited':
            self.status.set_attributes(self.blue_color);
        else:
            return
        self.status.set_text(status)

    # Предупреждающее сообщение
    def _alert(self, mtext):
        em = gtk.MessageDialog(self.ui.get_object('root_window'), 
            gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, 
            gtk.BUTTONS_CLOSE, str(mtext))
        em.run()
        em.destroy() 

    #Получение кода (self.code)
    def _get_code(self):
        code_buffer = self.ui.get_object('code').get_buffer()
        self.code = code_buffer.get_text(code_buffer.get_start_iter(),
            code_buffer.get_end_iter())     

    #Выполнение кода (используется переменная image)
    def _ex_code(self, image):
        try:
            exec(self.code)
        except Exception, error:
            self._alert(str(error)) 

    #Сохранение файла
    def _save_img(self, img):
        format = self.ui.get_object('format_combo').get_active()        
        if (format != 2) and (img.layers.__len__() > 1):
            pdb.gimp_image_flatten(img)
        layer = img.layers[0]
        root_filename = path.splitext(path.basename(img.filename))[0]
        filename = path.join(
            self.ui.get_object('dir_select').get_filename(),
            path.splitext(path.basename(img.filename))[0] \
            + ('.jpg', '.tif', '.xcf')[format])
        #JPG
        if format == 0:
            compress = self.ui.get_object('hscale1').get_value()
            pdb.file_jpeg_save(img, layer, filename, filename, compress,
                0, 0, 0, "Resized", 1, 0, 0, 2)
        #TIFF
        elif format == 1:
            compress = int(self.ui.get_object('checkbutton1').get_active())
            pdb.file_tiff_save(img, layer, filename, filename, compress)
        #XCF
        elif format == 2:
            pdb.gimp_xcf_save(0, img, layer, filename, filename)

    #Заполнение списка
    def _get_macro_list(self):
        macro_list = self.ui.get_object('liststore1')
        macro_list.clear()
        for key in sorted(self.base.keys()):
            list_iter = macro_list.append(None)
            macro_list[list_iter] = (key, self.base[key]['descr'])

    #Сброс редактора и текущего фрагмента
    def _clear_editor(self):
        self._ckey = ''
        self.ui.get_object('entry_descr').set_text('')
        self.ui.get_object('code').get_buffer().set_text('')
        self._set_status('New')


    #Генератор ключей
    def _keygen(self):
        if self.base.keys():
            return '%05d' %(int(sorted(self.base.keys())[-1])+1)
        else:
            return '00000'

    def browse_response(self, dlg, response_id):
        if response_id != gtk.RESPONSE_APPLY:
            dlg.hide()
            return

        proc_name = dlg.get_selected()

        if not proc_name:
            return

        proc = pdb[proc_name]

        cmd = ''

        if len(proc.return_vals) > 0:
            cmd = ', '.join([x[1].replace('-', '_')
                            for x in proc.return_vals]) + ' = '

        cmd = cmd + 'pdb.%s' % proc.proc_name.replace('-', '_')

        if len(proc.params) > 0 and proc.params[0][1] == 'run-mode':
            params = proc.params[1:]
        else:
            params = proc.params

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

    #Hide PDB Brower
    def hide_browser(self, widget, event):
        widget.hide()
        return True                  

    #Выбор процедуры из меню
    def add_code(self, widget, insert_code):
        code_buffer = self.ui.get_object('code').get_buffer()
        code_buffer.insert_at_cursor(insert_code)

    #Add files to filelist
    def run_chooser(self, widget):
        add_dialog = gtk.FileChooserDialog("Add files..", None,
            gtk.FILE_CHOOSER_ACTION_OPEN,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        add_dialog.set_default_response(gtk.RESPONSE_OK)
        add_dialog.set_select_multiple(True)

        filter = gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        add_dialog.add_filter(filter)

        filter = gtk.FileFilter()
        filter.set_name("Images")
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

    #Код в редакторе изменен
    def code_changed(self, widget):
        if self.status.get_text()=='Saved':
            self._set_status('Edited')

    #Mask changed
    def mask_changed(self, widget):
        function_list = self.ui.get_object('liststore3')
        function_list.clear()
        query_mask = widget.get_text()
        pdb_list = pdb.query(query_mask)  
        pdb_list.sort()     
        for funcname in pdb_list:
            list_iter = function_list.append(None)
            function_list[list_iter] = (funcname, )

    #PDB Browser cursor changed
    def pdb_cursor(self, widget):
        function = self.ui.get_object('liststore3')[widget.get_cursor()[0]][0]
        pdb_proc = pdb[function]
        self.ui.get_object('pdb_buffer').set_text(pdb_proc.proc_blurb)

    #PDB Browser function select
    def pdb_select(self, widget, tree_path, column):
        function_name = widget.get_model()[tree_path][0]
        try:
            function = pdb[function_name]
        except Exception, e:
            return
        self.add_code(widget, function_name +'(' + reduce(lambda res,x: res+x[1]+', ',\
            function.params, '')[:-2] + ')')
        self.ui.get_object('root_window').present()
        self.ui.get_object('code').grab_focus()

    #key press (Enter, Save etc)
    def key_press(self, widget, event):
        if widget == self.ui.get_object('entry_descr')\
        and gtk.gdk.keyval_name(event.keyval) == 'Return':
            self.ui.get_object('code').grab_focus()
        elif (event.state & gtk.gdk.CONTROL_MASK)\
        and gtk.gdk.keyval_name(event.keyval) == 's':
            self.code_save(widget)

    #Новый фрагмент
    def create_fragment(self, widget):
        self._clear_editor()
        self.ui.get_object('notebook1').set_current_page(2)   

    # Движение вперед по вкладкам по кнопке "Вперед"    
    def click_forward(self, widget): 
        self.ui.get_object('notebook1').next_page()

    # Сохранение отредактированного кода
    def code_save(self, widget):
        descr = self.ui.get_object('entry_descr').get_text()
        if descr == '':
            self._alert('Enter title!')
            return
        if self._ckey == '': self._ckey = self._keygen()        
        code_buffer = self.ui.get_object('code').get_buffer()
        code = code_buffer.get_text(
            code_buffer.get_start_iter(), code_buffer.get_end_iter())
        self._set_status('Saved')
        self.base[self._ckey] = {'descr':descr, 'code':code}
        self.base.sync()
        self._get_macro_list()

    # Выбор формата сохранения (переключение вкладки параметров сохранения)
    # Номера элементов списка и вкладок совпадают
    def format_changed(self, widget):
        self.ui.get_object('notebook2').set_current_page(widget.get_active())

    #Выбор фрагмента кода
    def select_fragment(self, widget, tree_path, column):
        self._ckey = widget.get_model()[tree_path][0]
        self.ui.get_object('entry_descr').set_text(self.base[self._ckey]['descr'])
        self.ui.get_object('code').\
            get_buffer().set_text(self.base[self._ckey]['code'])
        self.ui.get_object('notebook1').set_current_page(2) 
        self._set_status('Saved')  

    #Удалить фрагмент
    def delete_fragment(self, widget):
        macro_list, sel_iter =\
            self.ui.get_object('treeview1').get_selection().get_selected()
        key = macro_list[sel_iter][0]
        del self.base[key]
        self.base.sync()
        self._get_macro_list()
        if key ==self._ckey: self._clear_editor()

    #По кнопке "Selected images": получение файлов, цикл по ним
    def do_selected(self, widget):
        self._get_code()
        filenames = (x[0] for x in self.ui.get_object('liststore4'))        
        self.ui.get_object('notebook2').set_current_page(3)  
        file_count = filenames.__len__()
        file_num = 0    
        for filename in filenames:
            file_num += 1
            self.ui.get_object('progress').set_fraction(
                float(file_num)/float(file_count))
            self.ui.get_object('current_file').set_text(filename
                + ' ('+str(file_num)+ '/'+str(file_count)+')')
            while gtk.events_pending():
               gtk.main_iteration(False)                        
            image = pdb.gimp_file_load(filename, filename)
            self._ex_code(image)   
            self._save_img(image)
            pdb.gimp_image_delete(image)  
        self.format_changed(self.ui.get_object('format_combo'))

    #По кнопке "Opened images": цикл по открытым файлам
    def do_opened(self, widget):
        self._get_code()
        image_list = gimp.image_list()
        count = image_list.__len__()
        num = 0
        for image in image_list:
            self.ui.get_object('progress').set_fraction(
                float(num)/float(count))
            self.ui.get_object('current_file').set_text(
                path.basename(image.filename)
                + ' ('+str(num)+ '/'+str(count)+')')
            while gtk.events_pending():
               gtk.main_iteration(False)  
            pdb.gimp_image_undo_group_start(image)
            self._ex_code(image)             
            pdb.gimp_image_undo_group_end(image)

    # Закрытие приложения
    def close_app(self, widget):
        self.base.close()
        gtk.main_quit()