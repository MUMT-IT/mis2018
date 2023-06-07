from flask import jsonify
from . import assetbp as asset
from app.asset.models import AssetItem


@asset.route('/api/room/extra-items')
def get_items():
    data = []
    duplicates = set()
    for item in AssetItem.query.all():
        if item.th_name not in duplicates and \
                not item.room_id \
                and item.reservable:
            data.append({
                'th_name': item.th_name,
                'en_name': item.en_name
            })
            duplicates.add(item.th_name)

    return jsonify(data)
