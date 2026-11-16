# LabConstrictor repository form

A web form that sets up a [LabConstrictor](https://cellmigrationlab.github.io/LabConstrictor-Site/) app repository for you, so that you do not have to edit its files by hand.

## Get Started

1. **Open the form: <https://labconstrictor-form.streamlit.app>**
2. If you find the following window, click on `Yes, get this app back up!`
   
   <img width="40%" height="40%" alt="image" src="https://github.com/user-attachments/assets/9960fcbb-cf8b-4202-b26b-14de749e64b7" />

3. When you arrive to this page, chose between `Initialise a repository` or `Upload or update notebooks`, please take a look into [What it does](#what-it-does) for further information
   
   <img width="1781" height="349" alt="image" src="https://github.com/user-attachments/assets/790a20cc-1e1c-4c76-97d1-4fe48496fc56" />

## What it does

The form opens a pull request on your repository; you review and merge it. It needs a GitHub Personal Access Token (classic). It can:

- **Initialise a repository** made from the LabConstrictor template. You give the project name, the first version, whether code cells are hidden, and optional welcome, header and icon images. The form fills in the template, converts the icon, writes a starter README and, if you describe your app, the `labconstrictor-app.yaml` file that lists it in the [App Centre](https://cellmigrationlab.github.io/LabConstrictor-Site/apps/).
- **Upload or update notebooks.** Each notebook goes to `notebooks/<name>/` together with its `requirements.yaml`.

The guides on the [LabConstrictor website](https://cellmigrationlab.github.io/LabConstrictor-Site/guides/) show where the form fits into making an app, step by step.

## Getting help

Questions and bugs: the [issue tracker](https://github.com/CellMigrationLab/LabConstrictor_streamlit/issues).

## For developers

Run the form on your computer (needs Python and `git`; the automated tests use Python 3.11):

```
pip install -r requirements.txt
streamlit run app.py
```

Run the tests:

```
python -m unittest discover -s tests -v
```

The test that initialises a copy of the template is skipped unless `LC_TEMPLATE_DIR` points to a clone of [CellMigrationLab/LabConstrictor](https://github.com/CellMigrationLab/LabConstrictor).

Where things are: `app.py` is the form, `placeholders.py` fills in the template, `manifest_form.py` and `app_manifest.py` write `labconstrictor-app.yaml`, and [schemas/README.md](schemas/README.md) says where the manifest schema comes from.

License: [MIT](LICENSE).
