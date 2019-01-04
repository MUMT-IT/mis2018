from flask import jsonify
from . import assetbp as asset
from models import AssetItem


@asset.route('/api/room/extra-items')
def get_items():
    data = []
    duplicates = set()
    for item in AssetItem.query.all():
        if item.name not in duplicates and \
                not item.room_id:
            data.append({
                'name': item.name,
            })
            duplicates.add(item.name)

    return jsonify(data)
