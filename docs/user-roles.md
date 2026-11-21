# Users, roles and category permissions

FriPeri uses **three account roles**. The initial account created during first-run setup is an **administrator**; pre-existing accounts are migrated to administrator access, preserving their previous permissions.

## Role matrix

| Capability | Content creator (`cc`) | Editor (`editor`) | Administrator (`admin`) |
| --- | --- | --- | --- |
| Sign in and access the dashboard | Own content | All content | All content |
| Create new posts | Assigned categories only | All categories | All categories |
| Edit existing posts | Own posts only | Any post | Any post |
| Delete posts | No | Yes | Yes |
| Create categories | Yes (automatically assigned) | Yes | Yes |
| Delete categories | No | Yes | Yes |
| Create, edit and delete custom pages | No | Yes | Yes |
| Edit About page and custom-home content | No | Yes | Yes |
| Change homepage mode and feed settings | No | No | Yes |
| Configure site design, menus, languages or contact details | No | No | Yes |
| Read contact submissions or manage backups | No | No | Yes |
| Create, update or delete user accounts | No | No | Yes |

The editor's homepage content controls are separate from the administrator's site-wide homepage mode and feed settings. Only an administrator can switch the homepage mode or edit global configuration.

## Manage accounts

Sign in as administrator and open **Configuration → Users** (`/admin/users`).

1. Create a username (3–64 characters using letters, digits, underscore, period or hyphen) and an initial password of at least eight characters.
2. Choose `cc`, `editor` or `admin`.
3. For `cc`, select one or more categories in the permission list. Editors and administrators have access to all categories.
4. Save. A user can sign in at `/login` with the new credentials.
5. Use the existing account form to change a role, update category permissions or set a new password. Leave password blank to keep it unchanged.

An administrator cannot delete their own account or demote themselves. The last administrator account cannot be removed or demoted. Deleting an account does **not** delete existing posts: their `author_id` is set to NULL and the content remains available for editors/administrators. Deletion invalidates the deleted user's v3 sessions.

## Creator ownership and categories

A content creator is allowed to select only categories explicitly assigned by an administrator or categories they successfully create. A newly created category is automatically added to its creator's allowed set. Trying to create a category with an existing name does not grant access to that existing category.

Creators must choose an assigned category when saving a post; **Uncategorized** is not available to them. The server rejects attempts to save to an unassigned category or to edit another author's post, even if someone manually constructs a URL or sends an HTTP request. Creators cannot delete posts or categories.

Previously existing posts do not have a creator assigned automatically. Editors/administrators can still manage these posts; creators cannot claim them merely by editing.

## Migration and storage

Schema migration runs automatically at startup and adds:

- `users.role` — `admin` for all existing accounts.
- `posts.author_id` — tracks the account that created new posts.
- `user_categories` — many-to-many category grants for content creators.

Existing posts, users, and categories are not deleted during migration. Back up SQLite and uploaded media before upgrading a production installation. A rollback to earlier application code may not understand the new permission model; use a matching application and database backup.

All authorization decisions happen on the server. Hidden navigation items and buttons are only a presentation aid, not an access-control mechanism.

## Testing

After updating a disposable installation, run:

```bash
python -m pip install -r requirements-dev.txt
python -m pip check
python -m pytest -q tests/
```

The new `tests/test_roles.py` checks role migration, post ownership, creator category grants, account management and editor restrictions. No GitHub Actions are used.
