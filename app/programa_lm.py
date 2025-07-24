import json
import math
import io
import pandas as pd
from collections import Counter
from flask import (Blueprint, render_template, request, redirect, url_for, session,
                   flash, jsonify, abort, send_file)
from sqlalchemy import func, exc
from sqlalchemy.exc import IntegrityError

from . import db_session
from .decorators import login_required, permission_required, csrf_required
from .utils import log_activity
from .models import OrdenLM, ColumnaLM, DatoCeldaLM

bp = Blueprint('lm', __name__)

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
@permission_required('programa_lm.view')
def programa_lm():
    try:
        page = request.args.get('page', 1, type=int)
        wip_order_filter = request.args.get('wip_order_filter', '').strip()
        item_filter = request.args.get('item_filter', '').strip()
        filtros = {'wip_order_filter': wip_order_filter, 'item_filter': item_filter}
        columnas = db_session.query(ColumnaLM).order_by(ColumnaLM.orden).all()

        # Si hay filtros, buscar en pendientes y aprobados
        if wip_order_filter or item_filter:
            # Pendientes
            query_pend = db_session.query(OrdenLM).filter(OrdenLM.status == 'Pendiente')
            if wip_order_filter:
                query_pend = query_pend.filter(OrdenLM.wip_order.ilike(f"%{wip_order_filter}%"))
            if item_filter:
                query_pend = query_pend.filter(OrdenLM.item.ilike(f"%{item_filter}%"))
            query_pend = query_pend.order_by(OrdenLM.timestamp.desc())
            pagination_pend = Pagination(query_pend, page, per_page=15)
            ordenes_pendientes = pagination_pend.items
            orden_ids_pend = [o.id for o in ordenes_pendientes]
            celdas_pend = db_session.query(DatoCeldaLM).filter(DatoCeldaLM.orden_id.in_(orden_ids_pend)).all()
            datos_celdas_pend = {(c.orden_id, c.columna_id): c for c in celdas_pend}

            # Aprobados
            query_apr = db_session.query(OrdenLM).filter(OrdenLM.status == 'Aprobada')
            if wip_order_filter:
                query_apr = query_apr.filter(OrdenLM.wip_order.ilike(f"%{wip_order_filter}%"))
            if item_filter:
                query_apr = query_apr.filter(OrdenLM.item.ilike(f"%{item_filter}%"))
            query_apr = query_apr.order_by(OrdenLM.timestamp.desc())
            pagination_apr = Pagination(query_apr, page, per_page=15)
            ordenes_aprobadas = pagination_apr.items
            orden_ids_apr = [o.id for o in ordenes_aprobadas]
            celdas_apr = db_session.query(DatoCeldaLM).filter(DatoCeldaLM.orden_id.in_(orden_ids_apr)).all()
            datos_celdas_apr = {(c.orden_id, c.columna_id): c for c in celdas_apr}

            # Duplicados solo de pendientes
            all_pending_orders = db_session.query(OrdenLM.id, OrdenLM.wip_order, OrdenLM.item).filter(OrdenLM.status == 'Pendiente').all()
            from collections import Counter
            wip_counts = Counter(o.wip_order for o in all_pending_orders)
            item_counts = Counter(o.item for o in all_pending_orders if o.item)
            duplicate_ids = {o.id for o in all_pending_orders if wip_counts[o.wip_order] > 1 or (o.item and item_counts[o.item] > 1)}

            return render_template('programa_lm.html',
                ordenes=ordenes_pendientes,
                columnas=columnas,
                datos=datos_celdas_pend,
                pagination=pagination_pend,
                duplicate_ids=duplicate_ids,
                filtros=filtros,
                ordenes_aprobadas=ordenes_aprobadas,
                datos_aprobados=datos_celdas_apr,
                pagination_aprobados=pagination_apr
            )
        else:
            # Solo pendientes (comportamiento original)
            query = db_session.query(OrdenLM).filter(OrdenLM.status == 'Pendiente')
            if wip_order_filter: query = query.filter(OrdenLM.wip_order.ilike(f"%{wip_order_filter}%"))
            if item_filter: query = query.filter(OrdenLM.item.ilike(f"%{item_filter}%"))
            query = query.order_by(OrdenLM.timestamp.desc())
            pagination = Pagination(query, page, per_page=15)
            ordenes_en_pagina = pagination.items
            all_pending_orders = db_session.query(OrdenLM.id, OrdenLM.wip_order, OrdenLM.item).filter(OrdenLM.status == 'Pendiente').all()
            from collections import Counter
            wip_counts = Counter(o.wip_order for o in all_pending_orders)
            item_counts = Counter(o.item for o in all_pending_orders if o.item)
            duplicate_ids = {o.id for o in all_pending_orders if wip_counts[o.wip_order] > 1 or (o.item and item_counts[o.item] > 1)}
            orden_ids = [o.id for o in ordenes_en_pagina]
            celdas = db_session.query(DatoCeldaLM).filter(DatoCeldaLM.orden_id.in_(orden_ids)).all()
            datos_celdas = {(c.orden_id, c.columna_id): c for c in celdas}

            return render_template('programa_lm.html', ordenes=ordenes_en_pagina, columnas=columnas, datos=datos_celdas, pagination=pagination, duplicate_ids=duplicate_ids, filtros=filtros)
    except exc.SQLAlchemyError as e:
        flash(f"Error crítico al cargar el programa LM: {e}", "danger")
        return redirect(url_for('production.dashboard'))

@bp.route('/aprobados')
@login_required
@permission_required('programa_lm.view')
def programa_lm_aprobados():
    try:
        page = request.args.get('page', 1, type=int)
        wip_order_filter = request.args.get('wip_order_filter', '').strip()
        item_filter = request.args.get('item_filter', '').strip()
        filtros = {'wip_order_filter': wip_order_filter, 'item_filter': item_filter}

        query = db_session.query(OrdenLM).filter(OrdenLM.status == 'Aprobada')
        if wip_order_filter: query = query.filter(OrdenLM.wip_order.ilike(f"%{wip_order_filter}%"))
        if item_filter: query = query.filter(OrdenLM.item.ilike(f"%{item_filter}%"))
        query = query.order_by(OrdenLM.timestamp.desc())

        pagination = Pagination(query, page, per_page=15)
        ordenes_aprobadas = pagination.items
        columnas = db_session.query(ColumnaLM).order_by(ColumnaLM.orden).all()
        orden_ids = [o.id for o in ordenes_aprobadas]
        celdas = db_session.query(DatoCeldaLM).filter(DatoCeldaLM.orden_id.in_(orden_ids)).all()
        datos_celdas = {(c.orden_id, c.columna_id): c for c in celdas}
        
        return render_template('lm_aprobados.html', ordenes=ordenes_aprobadas, columnas=columnas, datos=datos_celdas, pagination=pagination, filtros=filtros)
    except exc.SQLAlchemyError as e:
        flash(f"Error al cargar las órdenes aprobadas: {e}", "danger")
        return redirect(url_for('lm.programa_lm'))

@bp.route('/search')
@login_required
@permission_required('programa_lm.view')
def search_lm():
    wip_order_filter = request.args.get('wip_order_filter', '').strip()
    item_filter = request.args.get('item_filter', '').strip()
    filtros = {'wip_order_filter': wip_order_filter, 'item_filter': item_filter}
    
    ordenes = []
    if wip_order_filter or item_filter:
        query = db_session.query(OrdenLM)
        if wip_order_filter:
            query = query.filter(OrdenLM.wip_order.ilike(f"%{wip_order_filter}%"))
        if item_filter:
            query = query.filter(OrdenLM.item.ilike(f"%{item_filter}%"))
        ordenes = query.order_by(OrdenLM.timestamp.desc()).all()

    columnas = db_session.query(ColumnaLM).order_by(ColumnaLM.orden).all()
    orden_ids = [o.id for o in ordenes]
    celdas = db_session.query(DatoCeldaLM).filter(DatoCeldaLM.orden_id.in_(orden_ids)).all()
    datos_celdas = {(c.orden_id, c.columna_id): c for c in celdas}

    return render_template('lm_search_results.html', 
                           ordenes=ordenes, 
                           columnas=columnas, 
                           datos=datos_celdas, 
                           filtros=filtros)

@bp.route('/toggle_status/<int:orden_id>', methods=['POST'])
@login_required
@permission_required('programa_lm.edit')
@csrf_required
def toggle_status_lm(orden_id):
    try:
        orden = db_session.get(OrdenLM, orden_id)
        if orden:
            orden.status = 'Aprobada' if orden.status == 'Pendiente' else 'Pendiente'
            flash(f"Orden '{orden.wip_order}' marcada como {orden.status}.", "success")
            db_session.commit()
            log_activity("Cambio Estado Orden LM", f"Orden ID {orden.id} a '{orden.status}'", "PROGRAMA_LM")
        else: 
            flash("La orden no fue encontrada.", "danger")
    except Exception as e:
        db_session.rollback()
        flash(f"Error al cambiar estado: {e}", "danger")
    return redirect(request.referrer or url_for('lm.programa_lm'))

@bp.route('/update_cell', methods=['POST'])
@login_required
@permission_required('programa_lm.edit', 'programa_lm.admin')
@csrf_required
def update_cell_lm():
    try:
        data = request.json
        orden_id, columna_id = int(data.get('orden_id')), int(data.get('columna_id'))
        valor, estilos_dict = data.get('valor', None), data.get('estilos_css', None)
        
        columna = db_session.get(ColumnaLM, columna_id)
        if not columna: 
            return jsonify({'status': 'error', 'message': 'Columna no encontrada'}), 404
        
        if 'programa_lm.admin' not in session['permissions'] and not columna.editable_por_lm:
            return jsonify({'status': 'error', 'message': 'No tienes permiso para editar esta celda.'}), 403
        
        celda = db_session.query(DatoCeldaLM).filter_by(orden_id=orden_id, columna_id=columna_id).first()
        
        if not celda and ((valor is not None and valor.strip()) or (estilos_dict and any(estilos_dict.values()))):
            celda = DatoCeldaLM(orden_id=orden_id, columna_id=columna_id)
            db_session.add(celda)
            
        if celda:
            if valor is not None: 
                celda.valor = valor.strip()
            if estilos_dict is not None: 
                celda.estilos_css = json.dumps(estilos_dict) if any(estilos_dict.values()) else None
            
            if not (celda.valor and celda.valor.strip()) and not (celda.estilos_css and json.loads(celda.estilos_css)):
                db_session.delete(celda)
                log_activity("Limpieza Celda LM", f"Celda eliminada en Orden ID: {orden_id}, Col ID: {columna_id}")
            else:
                log_activity("Edición Celda LM", f"Orden ID: {orden_id}, Col: {columna.nombre}")
        
        db_session.commit()
        return jsonify({'status': 'success', 'message': 'Celda actualizada'})
        
    except Exception as e:
        db_session.rollback()
        log_activity("Error Celda LM", str(e), "Sistema", "Error")
        return jsonify({'status': 'error', 'message': f'Error del servidor: {str(e)}'}), 500

@bp.route('/add_row', methods=['POST'])
@login_required
@permission_required('programa_lm.edit')
@csrf_required
def add_row_lm():
    wip_order = request.form.get('wip_order', '').strip()
    if not wip_order:
        return jsonify({'status': 'error', 'message': "El campo 'WIP Order' es obligatorio y no puede consistir solo de espacios."})
    try:
        nueva_orden = OrdenLM(
            wip_order=wip_order,
            item=request.form.get('item', '').strip(),
            qty=request.form.get('qty', 1, type=int)
        )
        db_session.add(nueva_orden)
        db_session.commit()
        log_activity("Creación Fila LM", f"Nueva WIP Order: {wip_order}", "PROGRAMA_LM")
        return jsonify({'status': 'success', 'message': 'Nueva orden agregada correctamente.'})
    except IntegrityError:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': f"La WIP Order '{wip_order}' ya existe. No se pueden añadir duplicados."})
    except Exception as e:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': f"Ocurrió un error inesperado: {e}"})

@bp.route('/update_column_width', methods=['POST'])
@login_required
@permission_required('programa_lm.admin')
@csrf_required
def update_column_width():
    try:
        data = request.json
        col_id, new_width = data.get('columna_id'), data.get('width')
        columna = db_session.get(ColumnaLM, col_id)
        if columna:
            columna.ancho_columna = new_width
            db_session.commit()
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Columna no encontrada'}), 404
    except Exception as e:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/reorder_columns', methods=['POST'])
@login_required
@permission_required('programa_lm.admin')
@csrf_required
def reorder_columns():
    try:
        data = request.json
        ordered_ids = data.get('ordered_ids', [])
        for index, col_id_str in enumerate(ordered_ids):
            try:
                col_id = int(col_id_str)
                columna = db_session.get(ColumnaLM, col_id)
                if columna:
                    columna.orden = index
            except (ValueError, TypeError):
                continue
        db_session.commit()
        log_activity("Reordenar Columnas LM", "Nuevo orden guardado.", "ADMIN")
        return jsonify({'status': 'success', 'message': 'Orden de columnas guardado.'})
    except Exception as e:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@bp.route('/edit_row/<int:orden_id>', methods=['POST'])
@login_required
@permission_required('programa_lm.admin')
@csrf_required
def edit_row_lm(orden_id):
    try:
        orden = db_session.get(OrdenLM, orden_id)
        if not orden:
            flash("La orden que intentas editar no existe.", "danger")
            return redirect(url_for('lm.programa_lm'))

        new_wip = request.form.get('wip_order')
        new_item = request.form.get('item')
        new_qty = request.form.get('qty')
        
        if new_wip != orden.wip_order and db_session.query(OrdenLM).filter(OrdenLM.wip_order == new_wip).first():
            flash(f"El WIP Order '{new_wip}' ya pertenece a otra orden.", "danger")
            return redirect(url_for('lm.programa_lm'))
            
        orden.wip_order = new_wip
        orden.item = new_item
        orden.qty = int(new_qty)
        
        db_session.commit()
        log_activity("Edición Fila LM", f"Orden WIP '{new_wip}' (ID: {orden_id}) actualizada.", "ADMIN")
        flash("Orden actualizada correctamente.", "success")
        
    except Exception as e:
        db_session.rollback()
        flash(f"Error al editar la orden: {e}", "danger")
    
    return redirect(url_for('lm.programa_lm'))

@bp.route('/delete_row/<int:orden_id>', methods=['POST'])
@login_required
@permission_required('programa_lm.admin')
@csrf_required
def delete_row_lm(orden_id):
    try:
        orden = db_session.get(OrdenLM, orden_id)
        if orden:
            wip_order = orden.wip_order
            db_session.delete(orden)
            db_session.commit()
            log_activity("Eliminación Fila LM", f"Orden WIP '{wip_order}' (ID: {orden_id}) eliminada.", "ADMIN", "Seguridad", "Critical")
            flash(f"La orden '{wip_order}' ha sido eliminada.", "success")
        else:
            flash("La orden que intentas eliminar no existe.", "danger")
    except Exception as e:
        db_session.rollback()
        flash(f"Error al eliminar la orden: {e}", "danger")
    return redirect(url_for('lm.programa_lm'))

@bp.route('/add_column', methods=['POST'])
@login_required
@permission_required('programa_lm.admin')
@csrf_required
def add_column_lm():
    nombre_columna = request.form.get('nombre_columna')
    if not nombre_columna:
        flash("El nombre de la columna es obligatorio.", "danger")
    elif db_session.query(ColumnaLM).filter_by(nombre=nombre_columna).first():
        flash(f"La columna '{nombre_columna}' ya existe.", "warning")
    else:
        max_orden = db_session.query(func.max(ColumnaLM.orden)).scalar() or 100
        nueva_columna = ColumnaLM(nombre=nombre_columna, editable_por_lm=True, orden=max_orden + 1)
        db_session.add(nueva_columna)
        db_session.commit()
        log_activity("Creación Columna LM", f"Nueva columna creada: {nombre_columna}", "ADMIN")
        flash("Nueva columna agregada exitosamente.", "success")
    return redirect(url_for('lm.programa_lm'))

@bp.route('/delete_column/<int:columna_id>', methods=['POST'])
@login_required
@permission_required('programa_lm.admin')
@csrf_required
def delete_column_lm(columna_id):
    try:
        columna_a_eliminar = db_session.get(ColumnaLM, columna_id)
        if columna_a_eliminar:
            nombre_columna = columna_a_eliminar.nombre
            db_session.delete(columna_a_eliminar)
            db_session.commit()
            log_activity("Eliminación Columna LM", f"Columna '{nombre_columna}' (ID: {columna_id}) eliminada.", "ADMIN", "Seguridad", "Critical")
            flash(f"La columna '{nombre_columna}' y todos sus datos han sido eliminados.", "success")
        else:
            flash("La columna que intentas eliminar no existe.", "danger")
    except exc.SQLAlchemyError as e:
        db_session.rollback()
        flash(f"Error al eliminar la columna: {e}", "danger")
    return redirect(url_for('lm.programa_lm'))

@bp.route('/manage_columns', methods=['POST'])
@login_required
@permission_required('programa_lm.admin')
@csrf_required
def manage_columns():
    try:
        for key, value in request.form.items():
            if key.startswith('width_'):
                col_id = int(key.split('_')[1])
                columna = db_session.get(ColumnaLM, col_id)
                if columna:
                    columna.ancho_columna = int(value)
        
        nombre_nueva_columna = request.form.get('nombre_nueva_columna')
        if nombre_nueva_columna:
            if db_session.query(ColumnaLM).filter_by(nombre=nombre_nueva_columna).first():
                flash(f"La columna '{nombre_nueva_columna}' ya existe.", "warning")
            else:
                max_orden = db_session.query(func.max(ColumnaLM.orden)).scalar() or 100
                nueva_columna = ColumnaLM(nombre=nombre_nueva_columna, editable_por_lm=True, orden=max_orden + 1)
                db_session.add(nueva_columna)
                log_activity("Creación Columna LM", f"Nueva columna: {nombre_nueva_columna}")
                flash(f"Columna '{nombre_nueva_columna}' agregada.", "success")

        db_session.commit()
        log_activity("Gestión de Columnas LM", "Anchos y/o nuevas columnas guardados.")
        flash("Configuración de columnas actualizada.", "success")

    except Exception as e:
        db_session.rollback()
        flash(f"Error al gestionar las columnas: {e}", "danger")
        log_activity("Error Gestión Columnas LM", str(e), severity="Error")

    return redirect(url_for('lm.programa_lm'))

@bp.route('/export/excel')
@login_required
@permission_required('programa_lm.view')
def export_excel_lm():
    try:
        ordenes = db_session.query(OrdenLM).filter(OrdenLM.status == 'Pendiente').order_by(OrdenLM.timestamp.desc()).all()
        if not ordenes:
            flash('No hay órdenes pendientes para exportar.', 'warning')
            return redirect(url_for('lm.programa_lm'))

        columnas = db_session.query(ColumnaLM).order_by(ColumnaLM.orden).all()
        orden_ids = [o.id for o in ordenes]
        celdas = db_session.query(DatoCeldaLM).filter(DatoCeldaLM.orden_id.in_(orden_ids)).all()
        datos_celdas = {(c.orden_id, c.columna_id): c.valor for c in celdas}
        
        records = []
        for o in ordenes:
            record = {
                'WIP Order': o.wip_order,
                'Item': o.item,
                'QTY': o.qty,
                'Status': o.status,
                'Fecha Creación': o.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            }
            for col in columnas:
                record[col.nombre] = datos_celdas.get((o.id, col.id), '')
            records.append(record)
        
        df = pd.DataFrame(records)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Ordenes_Pendientes_LM')
            workbook = writer.book
            worksheet = writer.sheets['Ordenes_Pendientes_LM']
            header_format = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#D7E4BC', 'border': 1})
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 20)
        output.seek(0)
        
        log_activity("Exportación Excel LM", f"{len(records)} órdenes exportadas.", "PROGRAMA_LM")
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name='Programa_LM_Pendientes.xlsx')

    except Exception as e:
        log_activity("Error Exportación Excel LM", str(e), "Sistema", "Error")
        flash(f"Ocurrió un error al generar el archivo Excel: {e}", "danger")
        return redirect(url_for('lm.programa_lm'))