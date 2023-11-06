import os
import csv
from uuid import uuid4
from flask import Flask, request, render_template, make_response, send_file, redirect
from glob import glob
from pathlib import Path
from decouple import config
import requests


DATASET_DIR = config("DATASET_DIR", default="./dataset/")

app = Flask(__name__)


images, ds_list = {}, []


def load_dataset():
    global images, ds_list
    for img_set_metadata_file in glob(os.path.join(DATASET_DIR, "**/*.csv"), recursive=True):
        img_set_metadata_file = Path(img_set_metadata_file)

        if img_set_metadata_file.parent not in images:
            print("Loading dataset:", img_set_metadata_file.parent.name)
        ds = images[img_set_metadata_file.parent] = []
        with open(img_set_metadata_file, "r") as f:
            csv_r = csv.DictReader(f)
            ds.extend(csv_r)
            for x in ds:
                x["full_path"] = img_set_metadata_file.parent.joinpath(x["file_name"])
                x["meta_file"] = img_set_metadata_file
                x["uuid"] = uuid4()

    ds_list = sorted(
        [v for l in images.values() for v in l], key=lambda o: o["full_path"]
    )


load_dataset()


def generate_caption(save_id):
    data = ds_list[save_id]
    file = data["full_path"]
    caption = requests.post(
        "http://localhost:8000/promptcap",
        files={"image": open(file, 'rb')}
    ).json()
    return caption["caption"]


def request_action(idx, action) -> int:
    if action == "prev":
        idx -= 1
    if action == "next" or action == "auto_caption_next":
        idx += 1
    return idx


def update_caption(row, new_caption):
    with open(row["meta_file"], "r+", newline="") as f:
        csv_file_read = csv.DictReader(f)
        data = [*csv_file_read]
        for r in data:
            if r["file_name"] == row["file_name"]:
                r["text"] = new_caption
                break
        f.seek(0)
        f.truncate()
        csv_file_writer = csv.DictWriter(
            f,
            fieldnames=csv_file_read.fieldnames,
            restval=csv_file_read.restval,
            dialect=csv_file_read.dialect,
            quoting=csv.QUOTE_ALL,
        )
        csv_file_writer.writeheader()
        csv_file_writer.writerows(data)


def save_image(img_id: int, new_caption: str):
    row = ds_list[img_id]
    if row["text"] != new_caption:
        print("Save image (id %d) with caption:" % img_id, new_caption)
        update_caption(row, new_caption)
        load_dataset()
        return True
    return False


@app.route("/", methods=["GET", "POST"])
def get_index():
    img_idx = request.cookies.get("image-idx", 0, type=int)
    auto_strip_input = request.cookies.get("caption-strip", 0, type=int)
    action = request.form.get("action")
    saved_changes = False

    if request.args.get("go"):
        response = redirect("/")
        try:
            for i, x in enumerate(ds_list):
                if x["uuid"].hex == request.args.get("go"):
                    img_idx = i
                    break
        except:
            pass
        response.set_cookie("image-idx", str(img_idx))
        return response

    if request.form.get("refresh"):
        load_dataset()

    if request.form.get("save_id"):
        auto_strip_input = int(request.form.get("auto_strip", 0, type=int))
        save_id = request.form.get("save_id", type=int)

        new_caption = request.form.get("caption")
        if auto_strip_input:
            new_caption = new_caption.strip()

        if action == "auto_caption" or action == "auto_caption_next":
            new_caption = generate_caption(save_id)

        saved_changes = save_image(save_id, new_caption)

    img_idx = request_action(img_idx, action)
    if img_idx < 0:
        img_idx = len(ds_list) - 1
    if img_idx >= len(ds_list):
        img_idx = 0

    data = ds_list[img_idx]

    params = {
        "image_url": f"/img/{img_idx}",
        "name": data["full_path"],
        "idx": img_idx,
        "caption": data["text"],
        "ds": ds_list,
        "uid": data["uuid"],
        "is_saved": saved_changes,
        "do_strip": bool(auto_strip_input),
    }

    response = make_response(render_template("index.j2.html", **params))
    response.set_cookie("image-idx", str(img_idx))
    response.set_cookie("caption-strip", str(auto_strip_input))
    return response


@app.route("/img/<int:id>")
def get_img(id: int):
    return send_file(ds_list[id]["full_path"])


if __name__ == "__main__":
    app.run(debug=True)
