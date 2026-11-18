from datetime import date
import sqlite3
from flask import Flask, flash, redirect, render_template, request, url_for
from database import get_connection, initialize_database

app = Flask(__name__)
app.secret_key = "library-demo-secret-key"
initialize_database()

@app.context_processor
def shared_template_values():
    return {"today_label": date.today().strftime("%A, %B %d, %Y")}


def loan_rows(status=None):
    """Return loans with the related book and member names."""
    query = """
        SELECT loans.*, books.title AS book_title, members.name AS member_name,
               CASE WHEN loans.status = 'Active' AND loans.due_date < ? THEN 1 ELSE 0 END AS overdue
        FROM loans JOIN books ON books.id = loans.book_id
        JOIN members ON members.id = loans.member_id
    """
    values = [date.today().isoformat()]
    if status:
        query += " WHERE loans.status = ?"
        values.append(status)
    query += " ORDER BY loans.status = 'Active' DESC, loans.due_date"
    with get_connection() as connection:
        return connection.execute(query, values).fetchall()


@app.route("/")
def dashboard():
    with get_connection() as connection:
        stats = {
            "books": connection.execute("SELECT COUNT(*) FROM books").fetchone()[0],
            "available": connection.execute("SELECT COUNT(*) FROM books WHERE available = 1").fetchone()[0],
            "members": connection.execute("SELECT COUNT(*) FROM members").fetchone()[0],
            "active_loans": connection.execute("SELECT COUNT(*) FROM loans WHERE status = 'Active'").fetchone()[0],
            "overdue": connection.execute("SELECT COUNT(*) FROM loans WHERE status = 'Active' AND due_date < ?", (date.today().isoformat(),)).fetchone()[0],
        }
    overdue_loans = [loan for loan in loan_rows("Active") if loan["overdue"]]
    return render_template("dashboard.html", stats=stats, overdue_loans=overdue_loans[:5])


@app.route("/books")
def books():
    search = request.args.get("q", "").strip()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM books WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ? OR category LIKE ? ORDER BY title",
            tuple(f"%{search}%" for _ in range(4)),
        ).fetchall()
    return render_template("books.html", books=rows, search=search)


@app.route("/books/add", methods=["GET", "POST"])
def add_book():
    return book_form()


@app.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
def edit_book(book_id):
    with get_connection() as connection:
        book = connection.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if not book:
        flash("That book could not be found.", "error")
        return redirect(url_for("books"))
    return book_form(book)


def book_form(book=None):
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        if not title or not author:
            flash("Please enter both a title and an author.", "error")
        else:
            year = request.form.get("publication_year", "").strip() or None
            details = (title, author, request.form.get("isbn", "").strip(), request.form.get("category", "").strip(), year)
            with get_connection() as connection:
                if book:
                    connection.execute("UPDATE books SET title=?, author=?, isbn=?, category=?, publication_year=? WHERE id=?", (*details, book["id"]))
                    flash("Book details saved.", "success")
                else:
                    connection.execute("INSERT INTO books (title, author, isbn, category, publication_year) VALUES (?, ?, ?, ?, ?)", details)
                    flash("Book added to the catalog.", "success")
            return redirect(url_for("books"))
    return render_template("book_form.html", book=book)


@app.route("/books/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    with get_connection() as connection:
        history = connection.execute("SELECT COUNT(*) FROM loans WHERE book_id=?", (book_id,)).fetchone()[0]
        if history:
            flash("A book with loan history cannot be removed. You can edit its details instead.", "error")
        else:
            connection.execute("DELETE FROM books WHERE id=?", (book_id,))
            flash("Book removed from the catalog.", "success")
    return redirect(url_for("books"))


@app.route("/members")
def members():
    search = request.args.get("q", "").strip()
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM members WHERE name LIKE ? OR email LIKE ? OR phone LIKE ? ORDER BY name", (f"%{search}%",) * 3).fetchall()
    return render_template("members.html", members=rows, search=search)


@app.route("/members/add", methods=["GET", "POST"])
def add_member():
    return member_form()


@app.route("/members/<int:member_id>/edit", methods=["GET", "POST"])
def edit_member(member_id):
    with get_connection() as connection:
        member = connection.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
    if not member:
        flash("That member could not be found.", "error")
        return redirect(url_for("members"))
    return member_form(member)


def member_form(member=None):
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Please enter the member's name.", "error")
        else:
            values = (name, request.form.get("email", "").strip(), request.form.get("phone", "").strip(), request.form.get("status", "Active"))
            with get_connection() as connection:
                if member:
                    connection.execute("UPDATE members SET name=?, email=?, phone=?, status=? WHERE id=?", (*values, member["id"]))
                    flash("Member details saved.", "success")
                else:
                    connection.execute("INSERT INTO members (name, email, phone, status) VALUES (?, ?, ?, ?)", values)
                    flash("Member registered.", "success")
            return redirect(url_for("members"))
    return render_template("member_form.html", member=member)


@app.route("/loans")
def loans():
    return render_template("loans.html", loans=loan_rows())


@app.route("/loans/checkout", methods=["GET", "POST"])
def checkout():
    with get_connection() as connection:
        available_books = connection.execute("SELECT id, title, author FROM books WHERE available=1 ORDER BY title").fetchall()
        active_members = connection.execute("SELECT id, name, email FROM members WHERE status='Active' ORDER BY name").fetchall()
        if request.method == "POST":
            book_id = request.form.get("book_id", type=int)
            member_id = request.form.get("member_id", type=int)
            due_date = request.form.get("due_date", "")
            book = connection.execute("SELECT * FROM books WHERE id=? AND available=1", (book_id,)).fetchone()
            member = connection.execute("SELECT * FROM members WHERE id=? AND status='Active'", (member_id,)).fetchone()
            if not book or not member:
                flash("Choose an available book and an active member.", "error")
            elif not due_date or due_date < date.today().isoformat():
                flash("Choose a due date today or later.", "error")
            else:
                connection.execute("INSERT INTO loans (book_id, member_id, checkout_date, due_date) VALUES (?, ?, ?, ?)", (book_id, member_id, date.today().isoformat(), due_date))
                connection.execute("UPDATE books SET available=0 WHERE id=?", (book_id,))
                flash("Checkout recorded. Happy reading!", "success")
                return redirect(url_for("loans"))
    return render_template("checkout_form.html", books=available_books, members=active_members, today=date.today().isoformat())


@app.route("/loans/<int:loan_id>/return", methods=["POST"])
def return_book(loan_id):
    with get_connection() as connection:
        loan = connection.execute("SELECT * FROM loans WHERE id=? AND status='Active'", (loan_id,)).fetchone()
        if not loan:
            flash("Only an active loan can be returned.", "error")
        else:
            connection.execute("UPDATE loans SET status='Returned', return_date=? WHERE id=?", (date.today().isoformat(), loan_id))
            connection.execute("UPDATE books SET available=1 WHERE id=?", (loan["book_id"],))
            flash("Book return recorded.", "success")
    return redirect(url_for("loans"))


if __name__ == "__main__":
    app.run(debug=True)

