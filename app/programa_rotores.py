import json
import math
import io
import pandas as pd
from flask import (Blueprint, render_template, request, redirect, url_for, session,
                   flash, jsonify, send_file)
from sqlalchemy import func, exc
from sqlalchemy.exc import IntegrityError

from . import db_session
from .decorators import login_required, permission_required, csrf_required
from .utils import log_activity
from .models import OrdenRotores, ColumnaRotores, DatoCeldaRotores

bp = Blueprint('rotores', __name__)

class Pagination:
    def __init__(self, query, page, per_page):
        self.query = query
        self.page = page
        self.per_page = per_page
        self.total_count = query.count()
        self.items = query.limit(per_page).offset((page - 1) * per_page).all()
    @property
    def pages(self): return math.ceil(self.total_count / self.per_page) if self.per_page > 0 else 0
    @property
    def has_prev(self): return self.page > 1
    @property
    def prev_num(self): return self.page - 1
    @property
    def has_next(self): return self.page < self.pages
    @property
    def next_num(self): return self.page + 1
    def iter_pages(self, left_edge=2, left_current=2, right_current=2, right_edge=2):
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or (self.page - left_current - 1 < num < self.page + right_current + 1) or num > self.pages - right_edge:
                if last + 1 != num: yield None
                yield num; last = num

@bp.route('/')
@login_required
@permission_required('programa_rotores.view')
def programa_rotores():
    try:
        page = request.args.get('page', 1, type=int)
        item_filter = request.args.get('item_filter', '').strip()
        item_number_filter = request.args.get('item_number_filter', '').strip()
        filtros = {'item_filter': item_filter, 'item_number_filter': item_number_filter}
        
        query = db_session.query(OrdenRotores).filter(OrdenRotores.status == 'Pendiente').order_by(OrdenRotores.timestamp.desc())
        
        if item_filter: query = query.filter(OrdenRotores.item.ilike(f"%{item_filter}%"))
        if item_number_filter: query = query.filter(OrdenRotores.item_number.ilike(f"%{item_number_filter}%"))
        
        pagination = Pagination(query, page, per_page=15)
        ordenes_en_pagina = pagination.items
        columnas = db_session.query(ColumnaRotores).order_by(ColumnaRotores.orden).all()
        orden_ids = [o.id for o in ordenes_en_pagina]
        celdas = db_session.query(DatoCeldaRotores).filter(DatoCeldaRotores.orden_id.in_(orden_ids)).all()
        datos_celdas = {(c.orden_id, c.columna_id): c for c in celdas}

        return render_template('programa_rotores.html', ordenes=ordenes_en_pagina, columnas=columnas, datos=datos_celdas, pagination=pagination, filtros=filtros)
    except exc.SQLAlchemyError as e:
        flash(f"Error crítico al cargar el programa de Rotores: {e}", "danger")
        return redirect(url_for('production.dashboard'))

@bp.route('/aprobados')
@login_required
@permission_required('programa_rotores.view')
def programa_rotores_aprobados():
    try:
        page = request.args.get('page', 1, type=int)
        item_filter = request.args.get('item_filter', '').strip()
        item_number_filter = request.args.get('item_number_filter', '').strip()
        filtros = {'item_filter': item_filter, 'item_number_filter': item_number_filter}

        query = db_session.query(OrdenRotores).filter(OrdenRotores.status == 'Aprobada').order_by(OrdenRotores.timestamp.desc())
        if item_filter: query = query.filter(OrdenRotores.item.ilike(f"%{item_filter}%"))
        if item_number_filter: query = query.filter(OrdenRotores.item_number.ilike(f"%{item_number_filter}%"))

        pagination = Pagination(query, page, per_page=15)
        ordenes_aprobadas = pagination.items
        columnas = db_session.query(ColumnaRotores).order_by(ColumnaRotores.orden).all()
        orden_ids = [o.id for o in ordenes_aprobadas]
        celdas = db_session.query(DatoCeldaRotores).filter(DatoCeldaRotores.orden_id.in_(orden_ids)).all()
        datos_celdas = {(c.orden_id, c.columna_id): c for c in celdas}
        
        return render_template('rotores_aprobados.html', ordenes=ordenes_aprobadas, columnas=columnas, datos=datos_celdas, pagination=pagination, filtros=filtros)
    except exc.SQLAlchemyError as e:
        flash(f"Error al cargar las órdenes aprobadas de Rotores: {e}", "danger")
        return redirect(url_for('rotores.programa_rotores'))

@bp.route('/search')
@login_required
@permission_required('programa_rotores.view')
def search_rotores():
    item_filter = request.args.get('item_filter', '').strip()
    item_number_filter = request.args.get('item_number_filter', '').strip()
    filtros = {'item_filter': item_filter, 'item_number_filter': item_number_filter}

    ordenes = []
    if item_filter or item_number_filter:
        query = db_session.query(OrdenRotores)
        if item_filter:
            query = query.filter(OrdenRotores.item.ilike(f"%{item_filter}%"))
        if item_number_filter:
            query = query.filter(OrdenRotores.item_number.ilike(f"%{item_number_filter}%"))
        ordenes = query.order_by(OrdenRotores.timestamp.desc()).all()

    columnas = db_session.query(ColumnaRotores).order_by(ColumnaRotores.orden).all()
    orden_ids = [o.id for o in ordenes]
    celdas = db_session.query(DatoCeldaRotores).filter(DatoCeldaRotores.orden_id.in_(orden_ids)).all()
    datos_celdas = {(c.orden_id, c.columna_id): c for c in celdas}

    return render_template('rotores_search_results.html', 
                           ordenes=ordenes, 
                           columnas=columnas, 
                           datos=datos_celdas, 
                           filtros=filtros)

@bp.route('/toggle_status/<int:orden_id>', methods=['POST'])
@login_required
@permission_required('programa_rotores.edit')
@csrf_required
def toggle_status_rotores(orden_id):
    try:
        orden = db_session.get(OrdenRotores, orden_id)
        if orden:
            orden.status = 'Aprobada' if orden.status == 'Pendiente' else 'Pendiente'
            flash(f"Orden '{orden.item}' marcada como {orden.status}.", "success")
            db_session.commit()
            log_activity("Cambio Estado Orden Rotores", f"Orden ID {orden.id} a '{orden.status}'", "PROGRAMA_ROTORES")
        else: 
            flash("La orden no fue encontrada.", "danger")
    except Exception as e:
        db_session.rollback()
        flash(f"Error al cambiar estado: {e}", "danger")
    return redirect(request.referrer or url_for('rotores.programa_rotores'))

@bp.route('/update_cell', methods=['POST'])
@login_required
@permission_required('programa_rotores.edit')
@csrf_required
def update_cell_rotores():
    try:
        data = request.json
        orden_id = int(data.get('orden_id'))
        columna_id = int(data.get('columna_id'))
        valor = data.get('valor', None)
        estilos_dict = data.get('estilos_css', None)
        
        celda = db_session.query(DatoCeldaRotores).filter_by(orden_id=orden_id, columna_id=columna_id).first()
        
        if not celda and ((valor is not None and valor.strip()) or (estilos_dict and any(estilos_dict.values()))):
            celda = DatoCeldaRotores(orden_id=orden_id, columna_id=columna_id)
            db_session.add(celda)
            
        if celda:
            if valor is not None:
                celda.valor = valor.strip()
            
            if estilos_dict is not None:
                celda.estilos_css = json.dumps(estilos_dict) if any(estilos_dict.values()) else None

            if not (celda.valor and celda.valor.strip()) and not celda.estilos_css:
                db_session.delete(celda)
        
        db_session.commit()
        return jsonify({'status': 'success', 'message': 'Celda actualizada'})
        
    except Exception as e:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/add_row', methods=['POST'])
@login_required
@permission_required('users.manage')
@csrf_required
def add_row_rotores():
    item = request.form.get('item', '').strip()
    if not item:
        return jsonify({'status': 'error', 'message': "El campo 'Item' es obligatorio y no puede consistir solo de espacios."})
    try:
        nueva_orden = OrdenRotores(
            item=item,
            item_number=request.form.get('item_number', '').strip(),
            cantidad=request.form.get('cantidad', 1, type=int)
        )
        db_session.add(nueva_orden)
        db_session.commit()
        log_activity("Creación Fila Rotores", f"Nuevo item: {item}", "PROGRAMA_ROTORES")
        return jsonify({'status': 'success', 'message': 'Nueva orden agregada correctamente.'})
    
    except IntegrityError:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': f"El item '{item}' ya existe. No se pueden añadir duplicados."})
    
    except Exception as e:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': f"Ocurrió un error inesperado: {e}"})

@bp.route('/edit_row/<int:orden_id>', methods=['POST'])
@login_required
@permission_required('users.manage')
@csrf_required
def edit_row_rotores(orden_id):
    try:
        orden = db_session.get(OrdenRotores, orden_id)
        if not orden:
            flash("La orden no existe.", "danger")
            return redirect(url_for('rotores.programa_rotores'))
            
        orden.item = request.form.get('item', '').strip()
        orden.item_number = request.form.get('item_number', '').strip()
        orden.cantidad = int(request.form.get('cantidad'))
        
        db_session.commit()
        log_activity("Edición Fila Rotores", f"Orden ID: {orden_id} actualizada.", "PROGRAMA_ROTORES")
        flash("Orden actualizada correctamente.", "success")
    except Exception as e:
        db_session.rollback()
        flash(f"Error al editar la orden: {e}", "danger")
    
    return redirect(url_for('rotores.programa_rotores'))

@bp.route('/delete_row/<int:orden_id>', methods=['POST'])
@login_required
@permission_required('users.manage')
@csrf_required
def delete_row_rotores(orden_id):
    try:
        orden = db_session.get(OrdenRotores, orden_id)
        if orden:
            item = orden.item
            db_session.delete(orden)
            db_session.commit()
            log_activity("Eliminación Fila Rotores", f"Orden '{item}' eliminada.", "PROGRAMA_ROTORES", "Seguridad")
            flash(f"La orden '{item}' ha sido eliminada.", "success")
        else:
            flash("La orden no existe.", "danger")
    except Exception as e:
        db_session.rollback()
        flash(f"Error al eliminar la orden: {e}", "danger")
    return redirect(url_for('rotores.programa_rotores'))

@bp.route('/export/excel')
@login_required
@permission_required('programa_rotores.view')
def export_excel_rotores():
    try:
        ordenes = db_session.query(OrdenRotores).filter(OrdenRotores.status == 'Pendiente').order_by(OrdenRotores.timestamp.desc()).all()
        if not ordenes:
            flash('No hay órdenes pendientes para exportar.', 'warning')
            return redirect(url_for('rotores.programa_rotores'))

        columnas = db_session.query(ColumnaRotores).order_by(ColumnaRotores.orden).all()
        orden_ids = [o.id for o in ordenes]
        celdas = db_session.query(DatoCeldaRotores).filter(DatoCeldaRotores.orden_id.in_(orden_ids)).all()
        datos_celdas = {(c.orden_id, c.columna_id): c.valor for c in celdas}
        
        records = []
        for o in ordenes:
            record = {
                'Item': o.item,
                'Item Number': o.item_number,
                'Cantidad': o.cantidad,
                'Status': o.status,
                'Fecha Creación': o.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            }
            for col in columnas:
                record[col.nombre] = datos_celdas.get((o.id, col.id), '')
            records.append(record)
        
        df = pd.DataFrame(records)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Ordenes_Pendientes_Rotores')
            workbook = writer.book
            worksheet = writer.sheets['Ordenes_Pendientes_Rotores']
            header_format = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#D7E4BC', 'border': 1})
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 20)
        output.seek(0)
        
        log_activity("Exportación Excel Rotores", f"{len(records)} órdenes exportadas.", "PROGRAMA_ROTORES")
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name='Programa_Rotores_Pendientes.xlsx')

    except Exception as e:
        log_activity("Error Exportación Excel Rotores", str(e), "Sistema", "Error")
        flash(f"Ocurrió un error al generar el archivo Excel: {e}", "danger")
        return redirect(url_for('rotores.programa_rotores'))