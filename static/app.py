from flask import Flask, render_template, json, request
from flask_mysqldb import MySQL, MySQLdb
from flask import Flask, jsonify, request, session
import mysql.connector
from flask import redirect
from flask import url_for
from datetime import date

app = Flask(__name__)
 
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'minimarket_semesta'

app.secret_key = 'secret key'

mysql = MySQL(app)

@app.route('/kasir', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST' and 'nama_akun' in request.form and 'password' in request.form:
        nama_akun = request.form['nama_akun']
        password = request.form['password']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM login_akun WHERE username = % s AND password = % s', 
                       (nama_akun, password, ))
        kasir = cursor.fetchone()
        if kasir:
            session['loggedin'] = True
            session['id_akun'] = kasir['id_akun']
            session['username'] = kasir['username']
            session['nama_akun'] = kasir['nama_akun']
            session['password'] = kasir['password']
            print(kasir)
            return redirect(url_for('transaksi'))  # Redirect to /transaksi route
        else:
            msg = 'Incorrect username / password!'
    return render_template('login kasir.html', msg=msg)

@app.route('/admin', methods =['GET', 'POST'])
def login_admin():
    msg = ''
    if request.method == 'POST' and 'useradmin' in request.form and 'passadmin' in request.form:
        username = request.form['useradmin']
        print(username)
        password = request.form['passadmin']
        print(password)
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM login_akun WHERE username = %s AND password = %s AND username = %s', 
                       (username, password, 'admin'))
        admin = cursor.fetchone()
        if admin:
            session['loggedin'] = True
            session['id_akun'] = admin['id_akun']
            session['useradmin'] = admin['username']
            session['nama_akun'] = admin['nama_akun']
            session['adminpassword'] = admin['password']
            print(admin)
        return redirect(url_for('riwayat'))
    else:
        msg = 'Incorrect username / password !'
        return render_template('login admin.html', msg = msg)

@app.route('/logout')
def logout():
    if 'useradmin' in session:
        # Jika yang logout adalah admin
        session.pop('loggedin', None)
        session.pop('useradmin', None)
        session.pop('adminpassword', None)
        return redirect(url_for('login_admin'))
    elif 'username' in session:
        # Jika yang logout adalah kasir
        session.pop('loggedin', None)
        session.pop('username', None)
        session.pop('nama_akun', None)
        session.pop('password', None)
        return redirect(url_for('login'))
    else:
        return redirect(url_for('login'))

@app.route('/admin/riwayat', methods=['GET', 'POST'])
def riwayat():
    if 'loggedin' in session and session['useradmin']:
        if request.method == 'GET':
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            
            # Mengambil semua data transaksi
            cursor.execute("SELECT * FROM tbl_transaksi")
            riwayat_transaksi = cursor.fetchall()
        
            transaksi_list = []
            for row in riwayat_transaksi:
                transaksi_list.append({
                    'id_transaksi': row['id_transaksi'],
                    'no_nota': row['no_nota'],
                    'id_akun': row['id_akun'],
                    'id_produk': row['id_produk'],
                    'kuantitas_produk': row['kuantitas_produk'],
                    'harga_satuan': row['harga_satuan'],
                    'sub_total': row['sub_total'],
                    'tanggal_transaksi': row['tanggal_transaksi'],
                    'total_pembayaran': row['total_pembayaran'],
                    'dibayarkan': row['dibayarkan'],
                    'kembalian': row['kembalian']
                })
            
            # Hitung jumlah produk
            cursor.execute('SELECT COUNT(*) as jumlah FROM tbl_produk')
            result = cursor.fetchone()
            jumlah_produk = result['jumlah'] if result else 0
            
            # Hitung jumlah pemasukan
            cursor.execute('SELECT SUM(total_pembayaran) AS total_pemasukan FROM tbl_transaksi')
            result = cursor.fetchone()
            total_pemasukan = result['total_pemasukan'] if result else 0
            
            # Mengambil transaksi dari kasir dengan id_akun = 1
            cursor.execute('''
                SELECT 
                    k.id_akun,
                    k.nama_akun,
                    t.id_transaksi,
                    t.tanggal_transaksi,
                    t.total_pembayaran,
                    t.dibayarkan,
                    t.kembalian
                FROM 
                    login_akun k
                JOIN 
                    tbl_transaksi t ON k.id_akun = t.id_akun
                WHERE 
                    k.id_akun = 1
            ''')
            kasir_satu = cursor.fetchall()
        
            # Mengambil transaksi dari kasir dengan id_akun = 2
            cursor.execute('''
                SELECT 
                    k.id_akun,
                    k.nama_akun,
                    t.id_transaksi,
                    t.no_nota,
                    t.tanggal_transaksi,
                    t.total_pembayaran,
                    t.dibayarkan,
                    t.kembalian
                FROM 
                    login_akun k
                JOIN 
                    tbl_transaksi t ON k.id_akun = t.id_akun
                WHERE 
                    k.id_akun = 2
            ''')
            kasir_dua = cursor.fetchall()
            cursor.close()
            
            return render_template('dashboard admin.html', transaksi_list=transaksi_list, jumlah_produk=jumlah_produk, total_pemasukan=total_pemasukan, kasir_satu=kasir_satu, kasir_dua=kasir_dua)
    else:
        return redirect(url_for('login_admin'))


@app.route('/transaksi', methods=['GET', 'POST'])
def transaksi():
    if 'loggedin' in session:
        if request.method == 'POST':
            no_nota = request.form['no_nota']
            session['no_nota'] = no_nota
            tanggal = request.form['tanggal']
            session['tanggal'] = tanggal
            pilih_produk = request.form['id_produk']
            kuantitas_produk = int(request.form['kuantitas_produk'])
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * FROM tbl_produk WHERE id_produk = %s", (pilih_produk,))
            produk_data = cursor.fetchall()
            if not produk_data:
                return redirect(url_for('transaksi'))
            produk_list = session.get('produk_list', [])
            new_product = {
                'no_nota': no_nota,
                'id_produk': produk_data[0]['id_produk'],
                'nama_produk': produk_data[0]['nama_produk'],
                'kuantitas_produk': kuantitas_produk,
                'harga_satuan': produk_data[0]['harga_satuan'],
                'sub_total': kuantitas_produk * produk_data[0]['harga_satuan']
            }
            for produk in produk_list:
                if produk['id_produk'] == new_product['id_produk']:
                    produk['sub_total'] = produk['kuantitas_produk'] * produk['harga_satuan']
                    break
            else:
                produk_list.append(new_product)

            session['produk_list'] = produk_list
            total_pembayaran = sum(produk['sub_total'] for produk in produk_list)
            session['total_pembayaran'] = total_pembayaran
            nama_akun = session['nama_akun']
            print(nama_akun)

            return render_template('dashboard kasir.html', produk_list=session['produk_list'], total_pembayaran=total_pembayaran, tanggal=tanggal, no_nota=no_nota, nama_akun=nama_akun)
        else:
            username = session['username']
            nama_akun = session['nama_akun']
            print(nama_akun)
            return render_template('dashboard kasir.html', username=username, nama_akun=nama_akun)
    else:
        return redirect(url_for('login'))
    
@app.route('/transaksi/bayar', methods=['GET', 'POST'])
def bayar_transaksi():
    if 'loggedin' in session:
        if request.method == 'POST':
            # Ambil dan validasi nilai yang dibayarkan
            dibayarkan = request.form.get('dibayarkan')
            dibayarkan = int(dibayarkan)
            session['dibayarkan'] = dibayarkan
            print(type(dibayarkan))
            print(dibayarkan)
            # Ambil total pembayaran dari sesi
            total_pembayaran = session.get('total_pembayaran')
            if total_pembayaran is None:
                return "Total pembayaran tidak ditemukan di sesi.", 400
            print(type(total_pembayaran))
            # Hitung kembalian
            kembalian = dibayarkan - total_pembayaran
            session['kembalian'] = kembalian
            print(kembalian)
            # Ambil detail kasir dan transaksi dari sesi
            kasir = {'id_akun': session.get('id_akun')}
            nama_akun = session['nama_akun']
            print(nama_akun)
            no_nota = session.get('no_nota')
            tanggal = session.get('tanggal')
            produk_list = session.get('produk_list', [])
            if not produk_list:
                return "Produk list tidak ditemukan di sesi.", 400
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            for produk in produk_list:
                cursor.execute(
                    '''INSERT INTO tbl_transaksi 
                    (no_nota, id_akun, id_produk, kuantitas_produk, harga_satuan, sub_total, 
                    tanggal_transaksi, total_pembayaran, dibayarkan, kembalian) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                    (no_nota, kasir['id_akun'], produk['id_produk'], produk['kuantitas_produk'], produk['harga_satuan'], 
                    produk['sub_total'], tanggal, total_pembayaran, dibayarkan, kembalian)
                )
                print(f"Inserted row: {produk}")

            mysql.connection.commit()
            print("Transaksi dimasukkan ke database")
            cursor.close()

            # Hapus session yang tidak dibutuhkan lagi
            session.pop('produk_list', None)
            session.pop('total_pembayaran', None)

            # Redirect ke halaman transaksi dengan informasi kembalian dan total pembayaran
            return render_template('dashboard kasir.html', kembalian=kembalian, total_pembayaran=total_pembayaran, nama_akun=nama_akun)
        else:
            username = session['username']
            nama_akun = session['nama_akun']
            print(nama_akun)
            return render_template('dashboard kasir.html', username=username, nama_akun=nama_akun)
    else:
        return render_template('dashboard kasir.html')


@app.route('/produk', methods=['GET', 'POST'])
def produk():
    if 'loggedin' in session and session['useradmin']:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        if request.method == 'POST':
            if 'delete' in request.form:
                # Hapus produk
                id_produk = request.form['id_produk']
                cursor.execute('DELETE FROM tbl_produk WHERE id_produk = %s', (id_produk,))
                mysql.connection.commit()
                print('Data dihapus')
            else:
                # Tambah produk
                id_produk = request.form['id_produk']
                nama = request.form['nama_produk']
                harga = request.form['harga_produk']
                cursor.execute('INSERT INTO tbl_produk (id_produk, nama_produk, harga_satuan) VALUES (%s, %s, %s)', 
                               (id_produk, nama, harga))
                mysql.connection.commit()
                print('Data ditambahkan')

            cursor.close()
            return redirect(url_for('produk'))

        # menampilkan semua data produk
        cursor.execute('SELECT * FROM tbl_produk')
        produk_data = cursor.fetchall()
        produk_list = []
        for row in produk_data:
            produk_list.append({
                'id_produk': row['id_produk'],
                'nama_produk': row['nama_produk'],
                'harga_satuan': row['harga_satuan']
            })

        cursor.close()
        return render_template('managemen produk.html', produk_list=produk_list)
    else:
        return redirect(url_for('admin'))  # Redirect to login page if not logged in



@app.route('/produk/update', methods=['PUT', 'POST'])
def update_produk():
    if request.method == 'POST':
        id_produk = request.form['id_produk']
        print(id_produk)
        nama = request.form['edit_nama']
        print(nama)
        harga = request.form['edit_harga']
        print(harga)
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        sql = 'UPDATE tbl_produk SET nama_produk=%s, harga_satuan=%s WHERE id_produk=%s'
        sql_update = (nama, harga, id_produk)  # Define sql_update as a tuple
        cursor.execute(sql, sql_update)  # Pass sql_update as an argument
        mysql.connection.commit()
        print('Data berhasil diedit')
        return redirect(url_for('produk'))
    else:
        print('produk tidak ada')

@app.route('/akun', methods=['GET', 'POST'])
def akun():
    if 'loggedin' in session and session['useradmin']:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        if request.method == 'POST':
            if 'delete' in request.form:
                # Hapus akun kasir
                username = request.form['username']
                cursor.execute('DELETE FROM login_akun WHERE username = %s', (username,))
                mysql.connection.commit()
                print("akun dihapus")
            else:
                # Tambah akun kasir
                username = request.form['username']
                nama = request.form['nama_akun']
                password = request.form['password']
                cursor.execute('INSERT INTO login_akun (username, nama_akun, password) VALUES (%s, %s, %s)', (username, nama, password))
                mysql.connection.commit()
                print("akun ditambahkan")

            cursor.close()
            return redirect(url_for('akun'))

        # menampilkan semua data akun
        cursor.execute('SELECT * FROM login_akun')
        akun_kasir_data = cursor.fetchall()
        akun_kasir_list = []
        for row in akun_kasir_data:
            akun_kasir_list.append({
                'username': row['username'],
                'nama_akun': row['nama_akun'],
                'password': row['password']
            })
        
        cursor.close()
        return render_template('managemen akun.html', akun_kasir_list=akun_kasir_list)
    else:
        return redirect(url_for('admin'))  # Redirect to login page if not logged in


@app.route('/akun/edit', methods=['GET', 'POST'])
def edit_akun():
    if request.method == 'POST':
        username = request.form['username']
        print(username)
        nama = request.form['edit_nama']
        print(nama)
        password = request.form['password']
        print(password)
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        sql = 'UPDATE login_akun SET nama_akun=%s, password=%s WHERE username=%s'
        sql_update = (nama, password, username)  # Define sql_update as a tuple
        cursor.execute(sql, sql_update)  # Pass sql_update as an argument
        mysql.connection.commit()
        print("akun diubah")
        return redirect(url_for('akun'))
    else:
        print('akun tidak ada')


if __name__ == '_main_':
    app.run(debug=True)