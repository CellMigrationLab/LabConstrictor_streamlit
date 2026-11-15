# LabConstrictor repository initialiser

A Streamlit web form for [LabConstrictor](https://github.com/CellMigrationLab/LabConstrictor) app repositories. It is deployed at https://labconstrictor-form.streamlit.app (the app sleeps when idle, so the first load can be slow).

It does two things, each by opening a pull request on your repository with a GitHub Personal Access Token (classic):

- **Initialise a repository** made from the LabConstrictor template: you give the project name, the first version, whether code cells are hidden, and optional welcome, header and icon images. The form clones the repository, replaces the template placeholders (`placeholders.py`), turns the icon into `.ico` and `.icns`, writes a starter README and, if you describe the app, `labconstrictor-app.yaml` for the LabConstrictor App Centre (`manifest_form.py`, `app_manifest.py`, checked against `schemas/labconstrictor-app.schema.json`).
- **Upload or update notebooks**: each notebook with its `requirements.yaml` goes to `notebooks/<name>/`.

## Run it locally

Needs Python (CI uses 3.11) and `git` on the PATH.

```
pip install -r requirements.txt
streamlit run app.py
```

## Tests

```
python -m unittest discover -s tests -v
```

The test that initialises a copy of the template is skipped unless `LC_TEMPLATE_DIR` points to a clone of [CellMigrationLab/LabConstrictor](https://github.com/CellMigrationLab/LabConstrictor). CI (`.github/workflows/tests.yml`) runs it against the template's `main` on every push, pull request and weekly.

`docs/labconstrictor-project.yaml` is how this project is listed on the LabConstrictor website. `schemas/README.md` says where the manifest schema comes from.

## License

[MIT](LICENSE)
