# Using Cabinet

[简体中文](guide.zh-CN.md) · [Back to the project](../README.md)

## Add an object

Open **新增藏品** (Add object), enter a name and category, then save with **收入藏阁**. The remaining details are optional.

Upload one JPEG, PNG, WebP, or GIF photo, or use an image URL. The image and form together must be under 10 MB. If you provide both, the uploaded photo takes priority. HEIC and multiple photos per object are not yet supported.

Enter as much of the acquisition date as you remember: a year, a year and month, or a complete date. Leave all three fields blank if you do not know it.

Use the searchable country/area and city selectors to record a location. If a town is not listed, leave the city blank and put the precise location in the source field. Prices are optional; after entering an amount, select a currency or use the local-currency shortcut.

The current version supports adding and viewing objects; editing and deleting them through the interface are not yet available.

## Revisit places

Open **旅迹** (Journeys) to switch between the timeline and world map. Both views can filter by acquisition year.

On the map, select a marker or place button to see its objects. Use the zoom controls and drag to explore. Objects without a selected city remain in the timeline and in the map's unlocated list.

## Back up your collection

Stop the app, then copy both of these from the project folder:

- `museum.db` — your collection records.
- `storage/` — your uploaded photos.

Restore both to the same locations before starting the app again. They are excluded from Git, so pushing the project to GitHub does not back up your collection.

## Local use

Keep the default localhost address. Cabinet currently has no authentication and is intended for use on your own computer.

The map and city search work locally. Images added by URL and fonts from Google Fonts require an Internet connection.
