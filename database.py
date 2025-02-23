import sys
from flask import Flask
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '' 
app.config['MYSQL_DB'] = 'hotel_reservas'

mysql = MySQL(app)

def criar_tabelas():
    with app.app_context():
        try:
            with mysql.connection.cursor() as cursor:
                # Criação da tabela de hóspedes
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospedes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nome VARCHAR(100) NOT NULL,
                    cpf VARCHAR(14) NOT NULL UNIQUE,
                    telefone VARCHAR(15),
                    email VARCHAR(100) UNIQUE
                );
                """)

                # Criação da tabela de quartos
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS quartos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    numero INT NOT NULL UNIQUE,
                    tipo VARCHAR(50) NOT NULL,
                    capacidade INT NOT NULL,
                    descricao TEXT,
                    preco DECIMAL(10, 2) NOT NULL
                );
                """)

                # Criação da tabela de reservas
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS reservas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    hospede_id INT NOT NULL,
                    quarto_id INT NOT NULL,
                    check_in DATE NOT NULL,
                    check_out DATE NOT NULL,
                    total DECIMAL(10, 2),
                    FOREIGN KEY (hospede_id) REFERENCES hospedes(id) ON DELETE CASCADE,
                    FOREIGN KEY (quarto_id) REFERENCES quartos(id) ON DELETE CASCADE
                );
                """)

                # Criação da tabela de usuários
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nome VARCHAR(100) NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    senha VARCHAR(255) NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE
                );
                """)

                # Criação do usuário administrador
                hashed_password = generate_password_hash('admin123')
                cursor.execute("""
                INSERT INTO usuarios (nome, email, senha, is_admin) 
                SELECT 'Administrador', 'adm@gmail.com', %s, TRUE 
                WHERE NOT EXISTS (SELECT * FROM usuarios WHERE email = 'adm@gmail.com');
                """, (hashed_password,))

                # Criação da tabela de logs (SEM FOREIGN KEY)
                cursor.execute("DROP TABLE IF EXISTS logs_reservas;")
                cursor.execute("""
                CREATE TABLE logs_reservas (
                    id_log INT AUTO_INCREMENT PRIMARY KEY,
                    operacao VARCHAR(10),
                    id_reserva INT,  -- Removida a foreign key
                    usuario VARCHAR(100),
                    data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """)

                # Função calcular_valor_reserva
                cursor.execute("DROP FUNCTION IF EXISTS calcular_valor_reserva;")
                cursor.execute("""
                CREATE FUNCTION calcular_valor_reserva(
                    p_check_in DATE,
                    p_check_out DATE,
                    p_quarto_id INT
                ) 
                RETURNS DECIMAL(10, 2)
                BEGIN
                    DECLARE total DECIMAL(10, 2) DEFAULT 0;
                    DECLARE dias INT;
                    DECLARE preco DECIMAL(10, 2);

                    SET dias = DATEDIFF(p_check_out, p_check_in);
                    IF dias <= 0 THEN
                        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Data de check-out deve ser maior que check-in!';
                    END IF;

                    SELECT q.preco INTO preco FROM quartos q WHERE q.id = p_quarto_id;
                    IF preco IS NULL THEN
                        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Quarto não encontrado!';
                    END IF;

                    SET total = dias * preco;
                    RETURN total;
                END;
                """)

                # Triggers para calcular o total da reserva
                cursor.execute("DROP TRIGGER IF EXISTS calcular_total_reserva_insert;")
                cursor.execute("""
                CREATE TRIGGER calcular_total_reserva_insert BEFORE INSERT ON reservas
                FOR EACH ROW
                BEGIN
                    SET NEW.total = calcular_valor_reserva(NEW.check_in, NEW.check_out, NEW.quarto_id);
                END;
                """)

                cursor.execute("DROP TRIGGER IF EXISTS calcular_total_reserva_update;")
                cursor.execute("""
                CREATE TRIGGER calcular_total_reserva_update BEFORE UPDATE ON reservas
                FOR EACH ROW
                BEGIN
                    SET NEW.total = calcular_valor_reserva(NEW.check_in, NEW.check_out, NEW.quarto_id);
                END;
                """)

                # Procedimento armazenado
                cursor.execute("DROP PROCEDURE IF EXISTS validar_reserva;")
                cursor.execute("""
                CREATE PROCEDURE validar_reserva(
                    IN p_hospede_id INT,
                    IN p_quarto_id INT,
                    IN p_check_in DATE,
                    IN p_check_out DATE
                )
                BEGIN
                    DECLARE disponibilidade INT;
                    DECLARE duplicado INT;

                    SELECT COUNT(*) INTO duplicado
                    FROM reservas
                    WHERE hospede_id = p_hospede_id
                    AND quarto_id = p_quarto_id
                    AND (
                        (p_check_in BETWEEN check_in AND check_out) OR
                        (p_check_out BETWEEN check_in AND check_out) OR
                        (check_in <= p_check_in AND check_out >= p_check_out)
                    );

                    IF duplicado > 0 THEN
                        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Reserva duplicada para o mesmo quarto e hóspede.';
                    END IF;

                    SELECT COUNT(*) INTO disponibilidade
                    FROM reservas
                    WHERE quarto_id = p_quarto_id
                    AND (
                        (p_check_in BETWEEN check_in AND check_out) OR
                        (p_check_out BETWEEN check_in AND check_out) OR
                        (check_in <= p_check_in AND check_out >= p_check_out)
                    );

                    IF disponibilidade > 0 THEN
                        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Quarto não disponível para as datas selecionadas.';
                    ELSE
                        INSERT INTO reservas (hospede_id, quarto_id, check_in, check_out)
                        VALUES (p_hospede_id, p_quarto_id, p_check_in, p_check_out);
                    END IF;
                END;
                """)

                # Triggers para logs de reservas (Corrigido)
                cursor.execute("DROP TRIGGER IF EXISTS log_reservas_insert;")
                cursor.execute("""
                CREATE TRIGGER log_reservas_insert
                AFTER INSERT ON reservas
                FOR EACH ROW
                BEGIN
                    INSERT INTO logs_reservas (operacao, id_reserva, usuario)
                    VALUES ('INSERT', NEW.id, 'Admin');
                END;
                """)

                cursor.execute("DROP TRIGGER IF EXISTS log_reservas_update;")
                cursor.execute("""
                CREATE TRIGGER log_reservas_update
                AFTER UPDATE ON reservas
                FOR EACH ROW
                BEGIN
                    INSERT INTO logs_reservas (operacao, id_reserva, usuario)
                    VALUES ('UPDATE', NEW.id, 'Admin');
                END;
                """)

                cursor.execute("DROP TRIGGER IF EXISTS log_reservas_delete;")
                cursor.execute("""
                CREATE TRIGGER log_reservas_delete
                BEFORE DELETE ON reservas
                FOR EACH ROW
                BEGIN
                    INSERT INTO logs_reservas (operacao, id_reserva, usuario)
                    VALUES ('DELETE', OLD.id, 'Admin');
                END;
                """)

            mysql.connection.commit()
            print("Configuração do banco de dados concluída com sucesso!")
        except Exception as e:
            print(f"Erro durante a configuração: {str(e)}")
            mysql.connection.rollback()

if __name__ == "__main__":
    criar_tabelas()