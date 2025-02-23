from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import MySQLdb  

app = Flask(__name__)
app.secret_key = "hotel"

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'hotel_reservas'

mysql = MySQL(app)

@app.template_filter('currency')
def currency(value):
    try:
        if value is not None:
            return f'R$ {value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except (ValueError, TypeError):
        return 'R$ 0,00'
    return 'R$ 0,00'

@app.template_filter('format_date')
def format_date(value):
    if value:
        return value.strftime('%d/%m/%Y')
    return ''

def calcular_valor_reserva(id_reserva):
    cur = mysql.connection.cursor()
    try:
        cur.execute("SELECT calcular_valor_reserva(%s)", (id_reserva,))
        total = cur.fetchone()[0]
        print(f"Total retornado da função SQL: {total}")
        if total is None:
            raise ValueError("Total retornado é None.")
    except Exception as e:
        print(f"Erro ao chamar função SQL: {e}")
        total = None
    finally:
        cur.close()
    return total

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    senha = request.form['senha']
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
    usuario = cur.fetchone()

    if usuario and check_password_hash(usuario[3], senha):
        session['user_id'] = usuario[0]
        session['user_name'] = usuario[1]
        session['is_admin'] = usuario[4]
        return redirect(url_for('index'))
    else:
        flash('Email ou senha incorretos!', 'error') 
        return redirect(url_for('login_page'))

@app.route('/index')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    is_admin = session.get('is_admin', False)
    return render_template('index.html', is_admin=is_admin)

@app.route('/cadastrar_usuario', methods=['GET', 'POST'])
def cadastrar_usuario():
    if 'user_id' not in session or not session.get('is_admin', False):
        flash('Você não tem permissão para acessar esta página.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        is_admin = request.form.get('is_admin') == 'on' 

        hashed_password = generate_password_hash(senha)

        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO usuarios (nome, email, senha, is_admin) VALUES (%s, %s, %s, %s)",
                        (nome, email, hashed_password, is_admin))
            mysql.connection.commit()
            flash('Usuário cadastrado com sucesso!', 'success')
        except MySQLdb.IntegrityError:
            mysql.connection.rollback()
            flash('Email já cadastrado!', 'error')
        
        is_admin = session.get('is_admin', False)
        return render_template('cadastrar_usuario.html', is_admin=is_admin)

    is_admin = session.get('is_admin', False)
    return render_template('cadastrar_usuario.html', is_admin=is_admin)

@app.route('/hospedes', methods=['GET', 'POST'])
def hospedes():
    cur = mysql.connection.cursor()
    order = request.args.get('order', 'asc')

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        cpf = request.form['cpf']
        telefone = request.form['telefone']
        
        try:
            cur.execute("INSERT INTO hospedes (nome, email, cpf, telefone) VALUES (%s, %s, %s, %s)", 
                        (nome, email, cpf, telefone))
            mysql.connection.commit()
            flash('Hóspede cadastrado com sucesso!', 'success')
        except MySQLdb.IntegrityError as e:
            mysql.connection.rollback()
            if 'cpf' in str(e):
                flash('CPF já cadastrado!', 'error')
            else:
                flash('Erro ao cadastrar hóspede. Tente novamente.', 'error')
        return redirect(url_for('hospedes'))

    if order == 'desc':
        cur.execute("SELECT * FROM hospedes ORDER BY nome DESC")
    else:
        cur.execute("SELECT * FROM hospedes ORDER BY nome ASC")

    hospedes = cur.fetchall()
    cur.close()
    is_admin = session.get('is_admin', False)
    return render_template('hospedes.html', hospedes=hospedes, order=order, is_admin=is_admin)

@app.route('/quartos', methods=['GET', 'POST'])
def quartos():
    cur = mysql.connection.cursor()
    order = request.args.get('order', 'asc')

    if request.method == 'POST':
        numero = request.form['numero']
        tipo = request.form['tipo']
        capacidade = request.form['capacidade']
        descricao = request.form['descricao']
        preco = request.form['preco']
        
        try:
            cur.execute("INSERT INTO quartos (numero, tipo, capacidade, descricao, preco) VALUES (%s, %s, %s, %s, %s)",
                        (numero, tipo, capacidade, descricao, preco))
            mysql.connection.commit()
            flash('Quarto cadastrado com sucesso!', 'success')
        except MySQLdb.IntegrityError as e:
            mysql.connection.rollback()
            if 'numero' in str(e):
                flash('Número do quarto já cadastrado!', 'error')
            else:
                flash('Erro ao cadastrar quarto. Tente novamente.', 'error')
        return redirect(url_for('quartos'))

    if order == 'desc':
        cur.execute("SELECT * FROM quartos ORDER BY numero DESC")
    else:
        cur.execute("SELECT * FROM quartos ORDER BY numero ASC")

    quartos = cur.fetchall()
    cur.close()
    is_admin = session.get('is_admin', False)
    return render_template('quartos.html', quartos=quartos, order=order, is_admin=is_admin)

@app.route('/reservas', methods=['GET', 'POST'])
def reservas():
    cur = mysql.connection.cursor()
    order = request.args.get('order', 'check_in')
    order_type = request.args.get('type', 'asc')

    if request.method == 'POST':
        usuario_id = request.form['hospede_id']
        quarto_id = request.form['quarto_id']
        check_in = request.form['check_in']
        check_out = request.form['check_out']

        try:
            # Chama o procedimento armazenado para validar e inserir a reserva
            cur.execute("CALL validar_reserva(%s, %s, %s, %s)", (usuario_id, quarto_id, check_in, check_out))
            mysql.connection.commit()

            # Log da reserva
            usuario_nome = session.get('user_name', 'Desconhecido')  # Nome do usuário da sessão
            cur.execute("INSERT INTO logs_reservas (operacao, id_reserva, usuario) VALUES ('INSERT', LAST_INSERT_ID(), %s)", (usuario_nome,))
            mysql.connection.commit()

            flash('Reserva cadastrada com sucesso!', 'success')
        except MySQLdb.Error as e:
            mysql.connection.rollback()
            flash(f'Erro: {str(e)}', 'error')
        finally:
            cur.close()
        return redirect(url_for('reservas'))

    order_clause = f"ORDER BY {order} {order_type}"
    try:
        cur.execute(f"""
            SELECT r.id, h.nome, q.numero, r.check_in, r.check_out, r.total 
            FROM reservas r 
            JOIN hospedes h ON r.hospede_id = h.id 
            JOIN quartos q ON r.quarto_id = q.id 
            {order_clause}
        """)
        data = cur.fetchall()
        
        cur.execute("SELECT id, nome FROM hospedes")
        users = cur.fetchall()

        cur.execute("SELECT id, numero FROM quartos")
        quartos = cur.fetchall()

    except Exception as e:
        flash(f'Erro ao carregar dados: {str(e)}', 'error')
        data = []
        users = []
        quartos = []

    finally:
        cur.close()

    is_admin = session.get('is_admin', False)
    return render_template('reservas.html', 
                         reservas=data, 
                         users=users, 
                         quartos=quartos, 
                         order=order, 
                         order_type=order_type, 
                         is_admin=is_admin)

@app.route('/relatorios', methods=['GET'])
def relatorios():
    cur = mysql.connection.cursor()
    search_query = request.args.get('search', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    total_por_hospede = []
    acima_2000 = []
    top_quartos = []
    nao_reservados = []

    if search_query == '' or search_query == 'total_por_hospede':
        total_query = """
            SELECT h.nome, SUM(r.total) AS total_gasto
            FROM reservas r
            JOIN hospedes h ON r.hospede_id = h.id
            WHERE (%s = '' OR r.check_in >= %s) AND (%s = '' OR r.check_in <= %s)
            GROUP BY h.id
            ORDER BY total_gasto DESC
        """
        cur.execute(total_query, (start_date, start_date, end_date, end_date))
        total_por_hospede = cur.fetchall()

    if search_query == 'acima_2000':
        acima_query = """
            SELECT h.nome, SUM(r.total) AS total_gasto
            FROM reservas r
            JOIN hospedes h ON r.hospede_id = h.id
            WHERE (%s = '' OR r.check_in >= %s) AND (%s = '' OR r.check_in <= %s)
            GROUP BY h.id
            HAVING total_gasto > 2000
            ORDER BY total_gasto DESC
        """
        cur.execute(acima_query, (start_date, start_date, end_date, end_date))
        acima_2000 = cur.fetchall()

    if search_query == 'top_quartos':
        top_query = """
            SELECT q.numero, COUNT(r.id) AS total_reservas
            FROM reservas r
            JOIN quartos q ON r.quarto_id = q.id
            WHERE (%s = '' OR r.check_in >= %s) AND (%s = '' OR r.check_in <= %s)
            GROUP BY q.id
            ORDER BY total_reservas DESC
            LIMIT 10
        """
        cur.execute(top_query, (start_date, start_date, end_date, end_date))
        top_quartos = cur.fetchall()

    if search_query == 'nao_reservados':
        nao_reservados_query = """
            SELECT q.numero
            FROM quartos q
            LEFT JOIN reservas r ON q.id = r.quarto_id AND (
                (%s = '' OR r.check_in >= %s) AND (%s = '' OR r.check_in <= %s)
            )
            WHERE r.id IS NULL
        """
        cur.execute(nao_reservados_query, (start_date, start_date, end_date, end_date))
        nao_reservados = cur.fetchall()

    cur.close()
    is_admin = session.get('is_admin', False)
    
    return render_template('relatorios.html', 
                           search_query=search_query,
                           start_date=start_date,
                           end_date=end_date,
                           total_por_hospede=total_por_hospede,
                           acima_2000=acima_2000,
                           top_quartos=top_quartos,
                           nao_reservados=nao_reservados,
                           is_admin=is_admin)

@app.route('/hospedes/edit/<int:id>', methods=['GET', 'POST'])
def edit_hospede(id):
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        cpf = request.form['cpf']
        telefone = request.form['telefone']
        
        cur.execute("""
            UPDATE hospedes 
            SET nome = %s, email = %s, cpf = %s, telefone = %s 
            WHERE id = %s
        """, (nome, email, cpf, telefone, id))
        mysql.connection.commit()
        flash('Hóspede atualizado com sucesso!', 'success')
        return redirect(url_for('hospedes'))

    cur.execute("SELECT * FROM hospedes WHERE id = %s", (id,))
    hospede = cur.fetchone()
    cur.close()
    
    is_admin = session.get('is_admin', False)
    return render_template('edit_hospede.html', hospede=hospede, is_admin=is_admin)

@app.route('/quartos/edit/<int:id>', methods=['GET', 'POST'])
def edit_quarto(id):
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        numero = request.form['numero']
        tipo = request.form['tipo']
        capacidade = request.form['capacidade']
        descricao = request.form['descricao']
        preco = request.form['preco']
        
        cur.execute("""
            UPDATE quartos 
            SET numero = %s, tipo = %s, capacidade = %s, descricao = %s, preco = %s 
            WHERE id = %s
        """, (numero, tipo, capacidade, descricao, preco, id))
        mysql.connection.commit()
        flash('Quarto atualizado com sucesso!', 'success')
        return redirect(url_for('quartos'))

    cur.execute("SELECT * FROM quartos WHERE id = %s", (id,))
    quarto = cur.fetchone()
    cur.close()
    
    is_admin = session.get('is_admin', False)
    return render_template('edit_quarto.html', quarto=quarto, is_admin=is_admin)

@app.route('/reservas/edit/<int:id>', methods=['GET', 'POST'])
def edit_reserva(id):
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        hospede_id = request.form['hospede_id']
        quarto_id = request.form['quarto_id']
        check_in = request.form['check_in']
        check_out = request.form['check_out']

        try:
            # Atualiza a reserva diretamente
            cur.execute("""
                UPDATE reservas 
                SET hospede_id = %s, quarto_id = %s, check_in = %s, check_out = %s 
                WHERE id = %s
            """, (hospede_id, quarto_id, check_in, check_out, id))
            mysql.connection.commit()
            flash('Reserva atualizada com sucesso!', 'success')

            # Log da edição da reserva
            usuario_nome = session.get('user_name', 'Desconhecido')  # Nome do usuário da sessão
            cur.execute("INSERT INTO logs_reservas (operacao, id_reserva, usuario) VALUES ('UPDATE', %s, %s)", (id, usuario_nome))
            mysql.connection.commit()

        except MySQLdb.Error as e:
            mysql.connection.rollback()
            flash(f'Erro ao atualizar reserva: {e}', 'error')

        finally:
            cur.close()

        return redirect(url_for('reservas'))

    try:
        cur.execute("SELECT * FROM reservas WHERE id = %s", (id,))
        reserva = cur.fetchone()

        cur.execute("SELECT id, nome FROM hospedes")
        users = cur.fetchall()

        cur.execute("SELECT id, numero FROM quartos")
        quartos = cur.fetchall()

    except Exception as e:
        flash(f'Erro ao carregar dados: {str(e)}', 'error')
        return redirect(url_for('reservas'))

    finally:
        cur.close()
    
    is_admin = session.get('is_admin', False)
    return render_template('edit_reserva.html', 
                         reserva=reserva, 
                         users=users, 
                         quartos=quartos, 
                         is_admin=is_admin)

@app.route('/hospedes/delete/<int:id>', methods=['POST'])
def delete_hospede(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM hospedes WHERE id = %s", [id])
    mysql.connection.commit()
    flash('Hóspede excluído com sucesso!', 'success')
    return redirect(url_for('hospedes'))

@app.route('/quartos/delete/<int:id>', methods=['POST'])
def delete_quarto(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM quartos WHERE id = %s", [id])
    mysql.connection.commit()
    flash('Quarto excluído com sucesso!', 'success')
    return redirect(url_for('quartos'))

@app.route('/reservas/delete/<int:id>', methods=['POST'])
def delete_reserva(id):
    cur = mysql.connection.cursor()
    
    try:
        # Primeiro, exclui a reserva
        cur.execute("DELETE FROM reservas WHERE id = %s", [id])
        mysql.connection.commit()
        
        # Log da exclusão da reserva
        usuario_nome = session.get('user_name', 'Desconhecido')  # Nome do usuário da sessão
        cur.execute("INSERT INTO logs_reservas (operacao, id_reserva, usuario) VALUES ('DELETE', %s, %s)", (id, usuario_nome))
        mysql.connection.commit()
        
        flash('Reserva excluída com sucesso!', 'success')
    except MySQLdb.Error as e:
        mysql.connection.rollback()
        flash(f'Erro ao excluir reserva: {e}', 'error')
    finally:
        cur.close()

    return redirect(url_for('reservas'))

@app.route('/logs')
def listar_logs():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'error')
        return redirect(url_for('index'))

    with app.app_context():
        try:
            with mysql.connection.cursor() as cursor:
                cursor.execute("SELECT * FROM logs_reservas ORDER BY data_hora DESC;")
                logs = cursor.fetchall()
                print(logs)  # Verificar se os logs estão sendo buscados corretamente
                return render_template('lista_logs.html', logs=logs, is_admin=session.get('is_admin'))
        except Exception as e:
            print(f"Erro ao buscar logs: {str(e)}")
            return render_template('lista_logs.html', logs=[], is_admin=session.get('is_admin'))

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('Você foi desconectado.', 'success') 
    return redirect(url_for('login_page'))

if __name__ == '__main__':
    app.run(debug=True)