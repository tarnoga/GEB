#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, shelve
from os import path
import pygtk
import gtk
from gimpfu import *
from gtkcodebuffer import CodeBuffer, SyntaxLoader, add_syntax_path

# test:
from pdb import set_trace


class BatchCodeExec:

    def __init__(self):
        _path = path.dirname(sys.modules[self.__module__].__file__)
        self.ui = gtk.Builder()
        self.ui.add_from_file(_path+'/batch_ex.ui')
        self.ui.connect_signals(self)
        add_syntax_path(_path)
        buff = CodeBuffer(lang=SyntaxLoader("python"))
        self.ui.get_object('code').set_buffer(buff)
        self.base = shelve.open(_path+'/batch_base')
        self.add_filters()
        self.get_macro_list()

    # Предупреждающее сообщение
    def alert(self, mtext):
        em = gtk.MessageDialog(self.ui.get_object('root_window'), 
            gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, 
            gtk.BUTTONS_CLOSE, str(mtext))
        em.run()
        em.destroy() 

    # Движение вперед по вкладкам по кнопке "Вперед"    
    def click_forward(self, widget): 
        self.ui.get_object('notebook1').next_page()

    # Сохранение отредактированного кода
    def code_save(self, widget):
        key = self.ui.get_object('entry_key').get_text()
        if not key:
            self.alert('Введите ключ')
            return
        descr = self.ui.get_object('entry_descr').get_text()
        code_buffer = self.ui.get_object('code').get_buffer()
        code = code_buffer.get_text(
            code_buffer.get_start_iter(), code_buffer.get_end_iter())
        self.base[key] = {'descr':descr, 'code':code}
        self.get_macro_list()

    # Выбор формата сохранения (переключение вкладки параметров сохранения)
    # Номера элементов списка и вкладок совпадают
    def format_changed(self, widget):
        self.ui.get_object('notebook2').set_current_page(widget.get_active())

    #Выбор страницы
    def select_page(self, widget, page, page_num):
        if page_num == 2:
            macro_list, sel_iter =\
                self.ui.get_object('treeview1').get_selection().get_selected()
            key = macro_list[sel_iter][0]
            code = self.base[key]['code']
            self.ui.get_object('entry_key').set_text(key)
            self.ui.get_object('entry_descr').set_text(self.base[key]['descr'])
            self.ui.get_object('code').\
                get_buffer().set_text(self.base[key]['code'])

    #Заполнение списка
    def get_macro_list(self):
        macro_list = self.ui.get_object('liststore1')
        macro_list.clear()
        for key in self.base.keys():
            list_iter = macro_list.append(None)
            macro_list[list_iter] = (key, self.base[key]['descr'])

    #Добавление фильтров
    def add_filters(self):
        file_chooser = self.ui.get_object('file_chooser')

        filter = gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        file_chooser.add_filter(filter)

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
        file_chooser.add_filter(filter)   

    #Получение кода (self.code)
    def get_code(self):
        code_buffer = self.ui.get_object('code').get_buffer()
        self.code = code_buffer.get_text(code_buffer.get_start_iter(),
            code_buffer.get_end_iter())         

    #Выполнение кода (используется переменная img)
    def ex_code(self, img):
        try:
            exec(self.code)
        except Exception, error:
            self.alert(str(error)) 

    #Сохранение файла
    def save_img(self, img):
        if img.layers.__len__() > 1:
            pdb.gimp_image_flatten(img)
        layer = img.layers[0]
        root_filename = path.splitext(path.basename(img.filename))[0]
        format = self.ui.get_object('format_combo').get_active()
        filename = path.join(
            self.ui.get_object('dir_select').get_filename(),
            path.splitext(path.basename(img.filename))[0] \
            + ('.jpg', '.tif')[format])
        #JPG
        if format == 0:
            compress = self.ui.get_object('hscale1').get_value()
            pdb.file_jpeg_save(img, layer, filename, filename, compress,
                0, 0, 0, "Resized", 1, 0, 0, 2)
        #TIFF
        elif format == 1:
            compress = int(self.ui.get_object('checkbutton1').get_active())
            pdb.file_tiff_save(img, layer, filename, filename, compress)

    #По кнопке Ok: получение файлов, цикл по ним
    def do_it(self, widget):
        self.get_code()
        filenames = self.ui.get_object('file_chooser').get_filenames()
        self.ui.get_object('notebook2').set_current_page(2)  
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
            img = pdb.gimp_file_load(filename, filename)
            self.ex_code(img)   
            self.save_img(img)
            pdb.gimp_image_delete(img)  
        self.format_changed(self.ui.get_object('format_combo'))

    # Закрытие приложения
    def close_app(self, widget):
        self.base.close()
        gtk.main_quit()