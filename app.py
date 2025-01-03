from flask import Flask, render_template, request, redirect, url_for, jsonify, session, json
from flask_mysqldb import MySQL, MySQLdb
import mysql.connector
import hashlib
import requests
from datetime import datetime
import logging

app = Flask(__name__)
 
app.config['MYSQL_HOST'] = 'dbsemesta.mysql.database.azure.com'
app.config['MYSQL_USER'] = 'adminsemesta'
app.config['MYSQL_PASSWORD'] = 'Semesta123'
app.config['MYSQL_DB'] = 'minimarket_semesta'
app.config['MYSQL_PORT'] = 3306


app.secret_key = 'secret key'

mysql = MySQL(app)

# Konfigurasi API Duitku
DUITKU_BASE_URL = "https://sandbox.duitku.com/webapi/api/merchant/v2/inquiry"
MERCHANT_CODE = "DS21366"  # Ganti dengan kode merchant Anda
MERCHANT_KEY = "d2a335e77105918ce19b9733f9e9fd52"  # Ganti dengan merchant key Anda



@app.route('/', methods=['GET', 'POST'])
def home():
    return redirect(url_for('login'))  # Mengarahkan ke fungsi 'login'

@app.route('/login', methods=['GET', 'POST'])
# @limiter.limit("3 per minute")  # Batasan 3 permintaan per menit
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return jsonify(success=False, error="Username dan password wajib diisi."), 400

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT id_akun, username, role FROM tbl_akun WHERE username = %s AND password = %s', (username, password))
        login = cursor.fetchone()
        print(login)

        if login:
            session['loggedin'] = True
            session['id_akun'] = login['id_akun']
            session['username'] = login['username']
            session['role'] = login['role']

            # Cek role kasir dan redirect sesuai dengan role
            if login['role'] == 'admin':
                return jsonify(success=True, redirect_url=url_for('riwayat'))  # Redirect ke riwayat jika role adalah admin
            elif login['role'] == 'kasir':
                return jsonify(success=True, redirect_url=url_for('transaksi'))  # Redirect ke transaksi jika role adalah kasir
            else:
                return jsonify(success=False, error="Role tidak valid!"), 403  # Jika role tidak valid
        else:
            return jsonify(success=False, error="Username atau password salah."), 401

    return render_template('login page.html')

@app.route('/logout')
def logout():
    if 'id_akun' in session:
        # Jika yang logout adalah admin
        session.pop('loggedin', None)
        session.pop('id_akun', None)
        session.pop('username', None)
        session.pop('password', None)
        return redirect(url_for('home'))
    else:
        return redirect(url_for('home'))

@app.route('/send_notification', methods=['POST'])
def send_notification():
    penerima = request.form.get('kasir')  # Dapatkan kasir yang dipilih
    pesan = request.form.get('pesan')    # Dapatkan pesan yang dikirimkan
    pengirim = "admin"                   # Pengirim adalah admin

    cur = mysql.connection.cursor()

    # Jika memilih "All User", kirim ke semua kasir
    if penerima == 'allkasir':  # All users
        users = cur.fetchall()
        for user in users:
            cur.execute("INSERT INTO tbl_chat (pengirim, penerima, chat) VALUES (%s, %s, %s, %s)", 
                        (pengirim, 'allkasir', pesan))  # 'kasir' sebagai penerima umum
        mysql.connection.commit()
    else:  # Kirim ke kasir tertentu
        cur.execute("INSERT INTO tbl_chat (pengirim, penerima, chat) VALUES (%s, %s, %s)", 
                    (pengirim, penerima, pesan))
        mysql.connection.commit()

    cur.close()
    return redirect(url_for('riwayat'))

@app.route('/notif/<username>', methods=['GET'])
def notif(username):
    username = session.get('username')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Query untuk mengambil pesan antara admin dan kasir tertentu
    query = """
    SELECT chat, waktu_chat FROM tbl_chat 
    WHERE pengirim = 'admin' AND (penerima = %s OR penerima = 'allkasir')
    ORDER BY waktu_chat ASC
    """
    cursor.execute(query, (username,))

    messages = cursor.fetchall()
    cursor.close()
    print(query)
    print(username)
    print(messages)
    return render_template('admin chat.html', messages=messages, username=username)


def generate_signature(merchant_code, merchant_order_id, payment_amount, api_key):
    data = f"{merchant_code}{merchant_order_id}{payment_amount}{api_key}"
    return hashlib.md5(data.encode()).hexdigest()

@app.route('/payment',  methods=['GET', 'POST'])
def duitku():
    try:
    # Ambil data dari session
        id_akun = session['id_akun']
        username = session['username']
        current_date = datetime.now().strftime("%Y%m%d")
        no_nota = session.get('no_nota')
        session_key = f"{no_nota}{current_date}"
        total_pembayaran = session.get('total_pembayaran')
        produk_list = session.get('produk_list', [])
        payment_method = request.form.get('paymentMethod')
        print(total_pembayaran)
        print(produk_list)
        print(payment_method)
        print(type(session_key))

        # Periksa apakah 'paymentAmount' ada di dalam data
        if not no_nota or not total_pembayaran or not produk_list:
            logging.error("Missing 'paymentAmount' in request data")
            return jsonify({'error': "'paymentAmount' is required"}), 400
        
        callback_url = "https://minimarketsemesta-a2bzf3fwd8a8fshq.canadacentral-01.azurewebsites.net/payment"  # URL untuk menerima notifikasi pembayaran
        return_url = "https://minimarketsemesta-a2bzf3fwd8a8fshq.canadacentral-01.azurewebsites.net/transaksi"
        
        # Hitung signature
        signature = generate_signature(MERCHANT_CODE, session_key, total_pembayaran, MERCHANT_KEY)

        # Tambahkan signature ke data payload
        params = {
            'merchantCode': MERCHANT_CODE,
            'paymentAmount': total_pembayaran,
            'paymentMethod': payment_method,
            'merchantOrderId': session_key,
            'productDetails': "pembelian produk",
            'customerVaName': "minimarketsemesta",
            'email': "minimarket@semesta.mail.com",
            'phoneNumber': '0856789101112',
            'callbackUrl': callback_url,
            'returnUrl': return_url,
            'signature': signature,
            'expiryPeriod': (10)
        }
        print(params)

        # Kirim permintaan ke endpoint transaksi Duitku
        url = 'https://sandbox.duitku.com/webapi/api/merchant/v2/inquiry'
        headers = {'Content-Type': 'application/json'}
        # response = requests.post(url, data=json.dumps(params), headers=headers)
        response = requests.post(url, json=params, headers=headers)

        if response.status_code == 200:
            result = response.json()
            logging.info(f"Transaction result: {result}")
            print(result)
            if result["statusCode"] == "00":
                # Redirect ke URL pembayaran yang diterima
                payment_url = result["paymentUrl"]
                return redirect(payment_url)  # Redirect user ke halaman pembayaran
        else:
            logging.error(f"Failed to create transaction, response: {response.text}")
            return jsonify({'error': 'Failed to create transaction', 'status_code': response.status_code, 'message': response.text}), 400

    except Exception as e:
        logging.error(f"Error creating transaction: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/payment/callback', methods=['POST'])
def duitku_callback():
    try:
        # Pastikan data diterima dengan benar
        data = request.form  # Jika data dikirim dalam form-data
        if not data:
            data = request.json  # Jika data dikirim dalam JSON
        
        # Debug data untuk memastikan formatnya
        logging.info(f"Callback Data: {data}")

        # Ambil parameter penting
        merchant_order_id = data.get('merchantOrderId')
        amount = data.get('amount')
        result_code = data.get('resultCode')
        signature = data.get('signature')

        # Validasi signature
        calculated_signature = hashlib.md5(
            f"{merchant_order_id}{amount}{MERCHANT_KEY}".encode()
        ).hexdigest()

        if signature == calculated_signature:
            if result_code == "00":
                # Transaksi berhasil
                logging.info(f"Transaction successful for Order ID: {merchant_order_id}")

                # Simpan status transaksi ke database atau sesi (opsional)
                session['transaksi_sukses'] = True
                session['no_nota'] = merchant_order_id

                # Redirect ke halaman transaksi
                return redirect(url_for('transaksi'))
            else:
                # Transaksi gagal
                logging.warning(f"Transaction failed for Order ID: {merchant_order_id}, Reason: {data.get('statusMessage')}")

                # Redirect ke halaman gagal
                return redirect(url_for('transaksi'))
        else:
            logging.error("Invalid signature in callback")
            return "Invalid signature", 400

    except Exception as e:
        logging.error(f"Error processing callback: {e}")
        return "Error processing callback", 500

    
@app.route('/transaksi', methods=['GET'])
def transaksi():
    if 'loggedin' in session:
        session['loggedin'] = True
        # Ambil data transaksi dari sesi
        id_akun = session['id_akun']
        username = session['username']
        if session.get('transaksi_sukses'):
            no_nota = session.get('no_nota')
            total_pembayaran = session.get('total_pembayaran')

            # Reset status transaksi sukses setelah ditampilkan
            session.pop('transaksi_sukses', None)
            return render_template('dashboard kasir.html', id_akun=id_akun, username=username, no_nota=no_nota,
                    total_pembayaran=total_pembayaran)
        return render_template('dashboard kasir.html', id_akun=id_akun, username=username)
    else:
        return redirect(url_for('login'))  # Redirect to login page if not logged in
    
@app.route('/transaksi', methods=['GET', 'POST'])
def input_transaksi():
    if request.method == 'POST':
        # Periksa apakah form untuk menambahkan produk atau pembayaran
        if 'id_produk' in request.form and 'kuantitas_produk' in request.form:
            # Proses menambahkan produk ke keranjang
            no_nota = request.form['no_nota']
            session['no_nota'] = no_nota
            tanggal = request.form['tanggal']
            session['tanggal'] = tanggal
            pilih_produk = request.form['id_produk']
            kuantitas_produk = int(request.form['kuantitas_produk'])
            print(kuantitas_produk)

            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * FROM tbl_produk WHERE id_produk = %s", (pilih_produk,))
            produk_data = cursor.fetchall()

            if not produk_data:
                print('Produk tidak ada')
                return redirect(url_for('transaksi'))

            # Ambil produk_list dari sesi
            produk_list = session.get('produk_list', [])

            # Tambahkan produk baru ke keranjang
            new_product = {
                'no_nota': no_nota,
                'id_produk': produk_data[0]['id_produk'],
                'nama_produk': produk_data[0]['nama_produk'],
                'kuantitas_produk': kuantitas_produk,
                'harga_satuan': produk_data[0]['harga_satuan'],
                'sub_total': kuantitas_produk * produk_data[0]['harga_satuan']
            }

            # Periksa apakah produk sudah ada di keranjang
            for produk in produk_list:
                if produk['id_produk'] == new_product['id_produk']:
                    produk['sub_total'] = produk['kuantitas_produk'] * produk['harga_satuan']
                    break
            else:
                # Tambahkan produk baru jika belum ada
                produk_list.append(new_product)

            session['produk_list'] = produk_list
            print(produk_list)
            total_pembayaran = int(sum(produk['sub_total'] for produk in produk_list))
            session['total_pembayaran'] = total_pembayaran
            print(total_pembayaran)
            username = session['username']
            return render_template('dashboard kasir.html', produk_list=produk_list, total_pembayaran=total_pembayaran, tanggal=tanggal, no_nota=no_nota, username=username)

        elif 'dibayarkan' in request.form:
            # Proses pembayaran
            dibayarkan = int(request.form['dibayarkan'])
            session['dibayarkan'] = dibayarkan

            total_pembayaran = session.get('total_pembayaran')
            if total_pembayaran is None:
                return "Total pembayaran tidak ditemukan di sesi.", 400

            # Hitung kembalian
            kembalian = dibayarkan - total_pembayaran
            session['kembalian'] = kembalian

            # Ambil detail kasir dan transaksi dari sesi
            kasir = {'id_akun': session.get('id_akun')}
            no_nota = session.get('no_nota')
            tanggal = session.get('tanggal')
            produk_list = session.get('produk_list', [])
            if not produk_list:
                return "Produk list tidak ditemukan di sesi.", 400

            # Simpan transaksi ke database
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            for produk in produk_list:
                cursor.execute(
                    '''INSERT INTO tbl_transaksi 
                    (no_nota, id_akun, id_produk, kuantitas_produk, harga_satuan, sub_total, tanggal_transaksi, total_pembayaran, dibayarkan, kembalian) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                    (no_nota, kasir['id_akun'], produk['id_produk'], produk['kuantitas_produk'], produk['harga_satuan'], produk['sub_total'], tanggal, total_pembayaran, dibayarkan, kembalian)
                )

            mysql.connection.commit()
            cursor.close()
            username = session['username']
            # Kembalikan data ke template
            session.pop('produk_list', None)
            session.pop('total_pembayaran', None)
            return render_template('dashboard kasir.html', kembalian=kembalian, username=username)

    # GET request, tampilkan halaman transaksi
    return render_template('dashboard kasir.html', produk_list=session.get('produk_list', []), total_pembayaran=session.get('total_pembayaran', 0), kembalian=session.get('kembalian', 0))

@app.route('/admin/riwayat', methods=['GET', 'POST'])
def riwayat():
    if 'loggedin' in session and session.get('role') == 'admin':
        if request.method == 'GET':
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            
            # Mengambil semua data transaksi
            cursor.execute("SELECT * FROM tbl_transaksi")
            riwayat_transaksi = cursor.fetchall()
        
            transaksi_list = []
            for row in riwayat_transaksi:
                transaksi_list.append({
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
                    k.username,
                    t.tanggal_transaksi,
                    t.total_pembayaran,
                    t.dibayarkan,
                    t.kembalian
                FROM 
                    tbl_akun k
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
                    k.username,
                    t.no_nota,
                    t.tanggal_transaksi,
                    t.total_pembayaran,
                    t.dibayarkan,
                    t.kembalian
                FROM 
                    tbl_akun k
                JOIN 
                    tbl_transaksi t ON k.id_akun = t.id_akun
                WHERE 
                    k.id_akun = 2
            ''')
            kasir_dua = cursor.fetchall()

            cursor.close()
            
            return render_template('dashboard admin.html', transaksi_list=transaksi_list, jumlah_produk=jumlah_produk, total_pemasukan=total_pemasukan)
    else:
        return redirect(url_for('login'))

@app.route('/produk', methods=['GET', 'POST'])
def produk():
    if 'loggedin' in session and session.get('role') == 'admin':
        # Pastikan session['id_akun'] dan session['username'] tersedia
        id_akun = session.get('id_akun')
        username = session.get('username')
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
                cursor.execute('INSERT INTO tbl_produk (id_produk, nama_produk, harga_satuan) VALUES (%s, %s, %s)', (id_produk, nama, harga))
                mysql.connection.commit()
                print('Data ditambahkan')

            cursor.close()
            return redirect(url_for('produk'))

        # Fetch all products
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
        return render_template('managemen produk.html', produk_list=produk_list, id_akun=id_akun, username=username)
    else:
        return redirect(url_for('admin'))  # Redirect to login page if not logged in


@app.route('/produk/update', methods=['PUT', 'POST'])
def update_produk():
    if 'loggedin' in session and session.get('role') == 'admin':
        # Pastikan session['id_akun'] dan session['username'] tersedia
        id_akun = session.get('id_akun')
        username = session.get('username')
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
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
            return redirect(url_for('produk', id_akun=id_akun, username=username))
        else:
            print('produk tidak ada')

@app.route('/akun', methods=['GET', 'POST'])
def akun():
    if 'loggedin' in session and session.get('role') == 'admin':
        # Pastikan session['id_akun'] dan session['username'] tersedia
        id_akun = session.get('id_akun')
        username = session.get('username')
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        if request.method == 'POST':
            if 'delete' in request.form:
                # Hapus akun kasir
                id_akun = request.form['id_akun']
                cursor.execute('DELETE FROM tbl_akun WHERE id_akun = %s', (id_akun,))
                mysql.connection.commit()
            else:
                # Tambah akun kasir
                username = request.form['username']
                email = request.form['email']
                password = request.form['password']
                role = request.form['role']

                cursor.execute('INSERT INTO tbl_akun (username, email, password, role) VALUES (%s, %s, %s, %s)', (username, email, password, role))
                mysql.connection.commit()

            cursor.close()
            return redirect(url_for('akun'))

        # Fetch all accounts
        cursor.execute('SELECT * FROM tbl_akun')
        akun_kasir_data = cursor.fetchall()
        akun_kasir_list = []
        print(akun_kasir_data)
        for row in akun_kasir_data:
            akun_kasir_list.append({
                'id_akun': row['id_akun'],
                'username': row['username'],
                'email': row['email'],
                'password': row['password']
            })
        
        cursor.close()
        return render_template('managemen akun.html', akun_kasir_list=akun_kasir_list, id_akun=id_akun)
    else:
        return redirect(url_for('admin'))  # Redirect to login page if not logged in


@app.route('/akun/edit', methods=['GET', 'POST'])
def edit_akun():
    if 'loggedin' in session:
        # Pastikan session['id_akun'] dan session['username'] tersedia
        id_akun = session.get('id_akun')
        username = session.get('username')
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        if request.method == 'POST':
            id_akun = request.form['id_akun']
            print(id_akun)
            nama = request.form['edit_nama']
            print(nama)
            password = request.form['password']
            print(password)
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            sql = 'UPDATE tbl_akun SET username=%s, password=%s WHERE id_akun=%s'
            sql_update = (nama, password, id_akun)  # Define sql_update as a tuple
            cursor.execute(sql, sql_update)  # Pass sql_update as an argument
            mysql.connection.commit()
            return redirect(url_for('akun', id_akun=id_akun, username=username))
        else:
            print('akun tidak ada')

def handle_rate_limit(e):
    return jsonify(success=False, error="Rate limit exceeded. Please wait a moment before trying again."), 429

if __name__ == '_main_':
    app.run(debug=True)
