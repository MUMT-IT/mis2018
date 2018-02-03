# TODO
## KPIs
* Add a feature that allows users to add a strategy template as a placeholder for some an orphan KPI.
* Add a feature that allows users to import strategies from other depts.
* Add a feature that allows users to create a group of users.
* Add a feature that allows users to tag a user group to a KPI.
* Add a feature that allows users to tag/group a KPI using a keyword.
* Modify the db schema to store revision history of KPIs.

## Students
* Edit timezone issue, store UTC to the database and display time using local timezone using tzlocal.get_localzone() and datetime.astimezone(tz). Note, Postgres store timezone aware datetime in UTC (probably). Better check the timezone every time setting up the app on a new server to be certain.

## Food
* Add a page for users to add produce and breeds.
