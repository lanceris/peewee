import datetime

from peewee import *

from .base import BaseTestCase


User = Table('users')
Tweet = Table('tweets')
Person = Table('person', ['id', 'name', 'dob'])
Note = Table('note', ['id', 'person_id', 'content'])


class TestSelectQuery(BaseTestCase):
    def test_select(self):
        query = (User
                 .select(User.c.id, User.c.username)
                 .where(User.c.username == 'foo'))
        self.assertSQL(query, (
            'SELECT "t1"."id", "t1"."username" '
            'FROM "users" AS "t1" '
            'WHERE ("t1"."username" = ?)'), ['foo'])

    def test_select_explicit_columns(self):
        query = (Person
                 .select()
                 .where(Person.dob < datetime.date(1980, 1, 1)))
        self.assertSQL(query, (
            'SELECT "t1"."id", "t1"."name", "t1"."dob" '
            'FROM "person" AS "t1" '
            'WHERE ("t1"."dob" < ?)'), [datetime.date(1980, 1, 1)])

    def test_join_explicit_columns(self):
        query = (Note
                 .select(Note.content)
                 .join(Person, on=(Note.person_id == Person.id))
                 .where(Person.name == 'charlie')
                 .order_by(Note.id.desc()))
        self.assertSQL(query, (
            'SELECT "t1"."content" '
            'FROM "note" AS "t1" '
            'INNER JOIN "person" AS "t2" ON ("t1"."person_id" = "t2"."id") '
            'WHERE ("t2"."name" = ?) '
            'ORDER BY "t1"."id" DESC'), ['charlie'])

    def test_multi_join(self):
        Like = Table('likes')
        LikeUser = User.alias('lu')
        query = (Like
                 .select(Tweet.c.content, User.c.username, LikeUser.c.username)
                 .join(Tweet, on=(Like.c.tweet_id == Tweet.c.id))
                 .join(User, on=(Tweet.c.user_id == User.c.id))
                 .join(LikeUser, on=(Like.c.user_id == LikeUser.c.id))
                 .where(LikeUser.c.username == 'charlie')
                 .order_by(Tweet.c.timestamp))
        self.assertSQL(query, (
            'SELECT "t1"."content", "t2"."username", "lu"."username" '
            'FROM "likes" AS "t3" '
            'INNER JOIN "tweets" AS "t1" ON ("t3"."tweet_id" = "t1"."id") '
            'INNER JOIN "users" AS "t2" ON ("t1"."user_id" = "t2"."id") '
            'INNER JOIN "users" AS "lu" ON ("t3"."user_id" = "lu"."id") '
            'WHERE ("lu"."username" = ?) '
            'ORDER BY "t1"."timestamp"'), ['charlie'])

    def test_correlated_subquery(self):
        Employee = Table('employee', ['id', 'name', 'salary', 'dept'])
        EA = Employee.alias('e2')
        query = (Employee
                 .select(Employee.id, Employee.name)
                 .where(Employee.salary > (EA
                                           .select(fn.AVG(EA.salary))
                                           .where(EA.dept == Employee.dept))))
        self.assertSQL(query, (
            'SELECT "t1"."id", "t1"."name" '
            'FROM "employee" AS "t1" '
            'WHERE ("t1"."salary" > ('
            'SELECT AVG("e2"."salary") '
            'FROM "employee" AS "e2" '
            'WHERE ("e2"."dept" = "t1"."dept")))'), [])

    def test_multiple_where(self):
        """Ensure multiple calls to WHERE are AND-ed together."""
        query = (Person
                 .select(Person.name)
                 .where(Person.dob < datetime.date(1980, 1, 1))
                 .where(Person.dob > datetime.date(1950, 1, 1)))
        self.assertSQL(query, (
            'SELECT "t1"."name" '
            'FROM "person" AS "t1" '
            'WHERE (("t1"."dob" < ?) AND ("t1"."dob" > ?))'),
            [datetime.date(1980, 1, 1), datetime.date(1950, 1, 1)])

    def test_simple_join(self):
        query = (User
                 .select(
                     User.c.id,
                     User.c.username,
                     fn.COUNT(Tweet.c.id).alias('ct'))
                 .join(Tweet, on=(Tweet.c.user_id == User.c.id))
                 .group_by(User.c.id, User.c.username))
        self.assertSQL(query, (
            'SELECT "t1"."id", "t1"."username", COUNT("t2"."id") AS ct '
            'FROM "users" AS "t1" '
            'INNER JOIN "tweets" AS "t2" ON ("t2"."user_id" = "t1"."id") '
            'GROUP BY "t1"."id", "t1"."username"'), [])

    def test_subquery(self):
        inner = (Tweet
                 .select(fn.COUNT(Tweet.c.id).alias('ct'))
                 .where(Tweet.c.user == User.c.id))
        query = (User
                 .select(User.c.username, inner.alias('iq'))
                 .order_by(User.c.username))
        self.assertSQL(query, (
            'SELECT "t1"."username", '
            '(SELECT COUNT("t2"."id") AS ct '
            'FROM "tweets" AS "t2" '
            'WHERE ("t2"."user" = "t1"."id")) AS "iq" '
            'FROM "users" AS "t1" ORDER BY "t1"."username"'), [])

    def test_user_defined_alias(self):
        UA = User.alias('alt')
        query = (User
                 .select(User.c.id, User.c.username, UA.c.nuggz)
                 .join(UA, on=(User.c.id == UA.c.id))
                 .order_by(UA.c.nuggz))
        self.assertSQL(query, (
            'SELECT "t1"."id", "t1"."username", "alt"."nuggz" '
            'FROM "users" AS "t1" '
            'INNER JOIN "users" AS "alt" ON ("t1"."id" = "alt"."id") '
            'ORDER BY "alt"."nuggz"'), [])

    def test_complex_select(self):
        Order = Table('orders', columns=(
            'region',
            'amount',
            'product',
            'quantity'))

        regional_sales = (Order
                          .select(
                              Order.region,
                              fn.SUM(Order.amount).alias('total_sales'))
                          .group_by(Order.region)
                          .cte('regional_sales'))

        top_regions = (regional_sales
                       .select(regional_sales.c.region)
                       .where(regional_sales.c.total_sales > (
                           regional_sales.select(
                               fn.SUM(regional_sales.c.total_sales) / 10)))
                       .cte('top_regions'))

        query = (Order
                 .select(
                     Order.region,
                     Order.product,
                     fn.SUM(Order.quantity).alias('product_units'),
                     fn.SUM(Order.amount).alias('product_sales'))
                 .where(
                     Order.region << top_regions.select(top_regions.c.region))
                 .group_by(Order.region, Order.product)
                 .with_cte(regional_sales, top_regions))

        self.assertSQL(query, (
            'WITH "regional_sales" AS ('
            'SELECT "a1"."region", SUM("a1"."amount") AS total_sales '
            'FROM "orders" AS "a1" '
            'GROUP BY "a1"."region"'
            '), '
            '"top_regions" AS ('
            'SELECT "regional_sales"."region" '
            'FROM "regional_sales" '
            'WHERE ("regional_sales"."total_sales" > '
            '(SELECT (SUM("regional_sales"."total_sales") / ?) '
            'FROM "regional_sales"))'
            ') '
            'SELECT "t1"."region", "t1"."product", '
            'SUM("t1"."quantity") AS product_units, '
            'SUM("t1"."amount") AS product_sales '
            'FROM "orders" AS "t1" '
            'WHERE ('
            '"t1"."region" IN ('
            'SELECT "top_regions"."region" '
            'FROM "top_regions")'
            ') GROUP BY "t1"."region", "t1"."product"'), [10])

    def test_compound_select(self):
        lhs = User.select(User.c.id).where(User.c.username == 'charlie')
        rhs = User.select(User.c.username).where(User.c.admin == True)
        q2 = (lhs | rhs)
        UA = User.alias('U2')
        q3 = q2 | UA.select(UA.c.id).where(UA.c.superuser == False)

        self.assertSQL(q3, (
            'SELECT "t1"."id" '
            'FROM "users" AS "t1" '
            'WHERE ("t1"."username" = ?) '
            'UNION '
            'SELECT "a1"."username" '
            'FROM "users" AS "a1" '
            'WHERE ("a1"."admin" = ?) '
            'UNION '
            'SELECT "U2"."id" '
            'FROM "users" AS "U2" '
            'WHERE ("U2"."superuser" = ?)'), ['charlie', True, False])


class TestInsertQuery(BaseTestCase):
    def test_insert_query(self):
        query = User.insert({
            User.c.username: 'charlie',
            User.c.superuser: False,
            User.c.admin: True})
        self.assertSQL(query, (
            'INSERT INTO "users" ("admin", "superuser", "username") '
            'VALUES (?, ?, ?)'), [True, False, 'charlie'])

    def test_insert_list(self):
        data = [
            {Person.name: 'charlie'},
            {Person.name: 'huey'},
            {Person.name: 'zaizee'}]
        query = Person.insert(data)
        self.assertSQL(query, (
            'INSERT INTO "person" ("name") VALUES (?), (?), (?)'),
            ['charlie', 'huey', 'zaizee'])

    def test_insert_query(self):
        source = User.select(User.c.username).where(User.c.admin == False)
        query = Person.insert(source, columns=[Person.name])
        self.assertSQL(query, (
            'INSERT INTO "person" ("name") '
            'SELECT "t1"."username" FROM "users" AS "t1" '
            'WHERE ("t1"."admin" = ?)'), [False])

    def test_insert_query_cte(self):
        cte = User.select(User.c.username).cte('foo')
        source = cte.select(cte.c.username)
        query = Person.insert(source, columns=[Person.name]).with_cte(cte)
        self.assertSQL(query, (
            'WITH "foo" AS (SELECT "a1"."username" FROM "users" AS "a1") '
            'INSERT INTO "person" ("name") '
            'SELECT "foo"."username" FROM "foo"'), [])


class TestUpdateQuery(BaseTestCase):
    def test_update_query(self):
        query = (User
                 .update({
                     User.c.username: 'nuggie',
                     User.c.admin: False,
                     User.c.counter: User.c.counter + 1})
                 .where(User.c.username == 'nugz'))
        self.assertSQL(query, (
            'UPDATE "users" SET '
            '"admin" = ?, '
            '"counter" = ("counter" + ?), '
            '"username" = ? '
            'WHERE ("username" = ?)'), [False, 1, 'nuggie', 'nugz'])

    def test_update_subquery(self):
        subquery = (User
                    .select(User.c.id, fn.COUNT(Tweet.c.id).alias('ct'))
                    .join(Tweet, on=(Tweet.c.user_id == User.c.id))
                    .group_by(User.c.id)
                    .having(SQL('ct') > 100))
        query = (User
                 .update({
                     User.c.muted: True,
                     User.c.counter: 0})
                 .where(User.c.id << subquery))
        self.assertSQL(query, (
            'UPDATE "users" SET '
            '"counter" = ?, '
            '"muted" = ? '
            'WHERE ("id" IN ('
            'SELECT "t1"."id", COUNT("t2"."id") AS ct '
            'FROM "users" AS "t1" '
            'INNER JOIN "tweets" AS "t2" '
            'ON ("t2"."user_id" = "t1"."id") '
            'GROUP BY "t1"."id" '
            'HAVING (ct > ?)))'), [0, True, 100])


class TestDeleteQuery(BaseTestCase):
    def test_delete_query(self):
        query = (User
                 .delete()
                 .where(User.c.username != 'charlie')
                 .limit(3))
        self.assertSQL(
            query,
            'DELETE FROM "users" WHERE ("username" != ?) LIMIT 3',
            ['charlie'])

    def test_delete_subquery(self):
        subquery = (User
                    .select(User.c.id, fn.COUNT(Tweet.c.id).alias('ct'))
                    .join(Tweet, on=(Tweet.c.user_id == User.c.id))
                    .group_by(User.c.id)
                    .having(SQL('ct') > 100))
        query = (User
                 .delete()
                 .where(User.c.id << subquery))
        self.assertSQL(query, (
            'DELETE FROM "users" '
            'WHERE ("id" IN ('
            'SELECT "t1"."id", COUNT("t2"."id") AS ct '
            'FROM "users" AS "t1" '
            'INNER JOIN "tweets" AS "t2" ON ("t2"."user_id" = "t1"."id") '
            'GROUP BY "t1"."id" '
            'HAVING (ct > ?)))'), [100])

    def test_delete_cte(self):
        cte = (User
               .select(User.c.id)
               .where(User.c.admin == True)
               .cte('u'))
        query = (User
                 .delete()
                 .where(User.c.id << cte.select(cte.c.id))
                 .with_cte(cte))
        self.assertSQL(query, (
            'WITH "u" AS '
            '(SELECT "a1"."id" FROM "users" AS "a1" WHERE ("a1"."admin" = ?)) '
            'DELETE FROM "users" '
            'WHERE ("id" IN (SELECT "u"."id" FROM "u"))'), [True])


Register = Table('register', ('id', 'value', 'category'))


class TestWindowQuery(BaseTestCase):
    def test_frame(self):
        query = (Register
                 .select(
                     Register.value,
                     fn.AVG(Register.value).over(
                         partition_by=[Register.category],
                         start=Window.preceding(),
                         end=Window.following(2))))
        self.assertSQL(query, (
            'SELECT "t1"."value", AVG("t1"."value") '
            'OVER (PARTITION BY "t1"."category" '
            'RANGE BETWEEN UNBOUNDED PRECEDING AND 2 FOLLOWING) '
            'FROM "register" AS "t1"'), [])

        query = (Register
                 .select(Register.value, fn.AVG(Register.value).over(
                     partition_by=[Register.category],
                     order_by=[Register.value],
                     start=SQL('CURRENT ROW'),
                     end=Window.following())))
        self.assertSQL(query, (
            'SELECT "t1"."value", AVG("t1"."value") '
            'OVER (PARTITION BY "t1"."category" '
            'ORDER BY "t1"."value" '
            'RANGE BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) '
            'FROM "register" AS "t1"'), [])

    def test_partition_unordered(self):
        partition = [Register.category]
        query = (Register
                 .select(
                     Register.category,
                     Register.value,
                     fn.AVG(Register.value).over(partition_by=partition))
                 .order_by(Register.id))
        self.assertSQL(query, (
            'SELECT "t1"."category", "t1"."value", AVG("t1"."value") '
            'OVER (PARTITION BY "t1"."category") '
            'FROM "register" AS "t1" ORDER BY "t1"."id"'), [])
