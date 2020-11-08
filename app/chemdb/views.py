#! -*- coding:utf-8 -*-
from flask import render_template, flash, redirect, url_for, request
from . import chemdbbp as chemdb
from app.main import db
from models import ChemItem
from forms import ChemItemForm


@chemdb.route('/')
def index():
    items = ChemItem.query.all()
    return render_template('chemdb/index.html', items=items)


@chemdb.route('/add', methods=['GET', 'POST'])
def add_item():
    form = ChemItemForm()
    if form.validate_on_submit():
        new_item = ChemItem()
        form.populate_obj(new_item)
        db.session.add(new_item)
        db.session.commit()
        flash('data has been recorded.', 'success')
        return redirect(url_for('chemdb.index'))
    return render_template('chemdb/form.html', form=form, title=u'เพิ่มรายการใหม่')


@chemdb.route('/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    item = ChemItem.query.get(item_id)
    if item:
        form = ChemItemForm(obj=item)
        if request.method == 'POST':
            if form.validate_on_submit():
                form.populate_obj(item)
                db.session.add(item)
                db.session.commit()

        return render_template('chemdb/form.html', form=form, title=u'แก้ไขข้อมูล')