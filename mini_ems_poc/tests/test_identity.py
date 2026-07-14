import tempfile
import unittest
from pathlib import Path

from mini_ems_poc.mini_ems_runtime.identity import IdentityStore


class IdentityStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.now = 1_700_000_000
        self.store = IdentityStore(Path(self.tmpdir.name), now=lambda: self.now)

    def bootstrap(self):
        return self.store.bootstrap_admin(
            bootstrap_code="existing-release-code",
            expected_code="existing-release-code",
            username="admin",
            display_name="Anlagenadmin",
            password="ein-langes-testpasswort",
        )

    def test_bootstrap_creates_hashed_admin_and_session(self) -> None:
        session = self.bootstrap()

        self.assertTrue(self.store.is_initialized())
        self.assertEqual(session.user.role, "admin")
        self.assertEqual(self.store.session_user(session.token).username, "admin")
        self.assertNotIn(b"ein-langes-testpasswort", self.store.path.read_bytes())

    def test_bootstrap_is_single_use_and_checks_existing_code(self) -> None:
        with self.assertRaises(PermissionError):
            self.store.bootstrap_admin(
                bootstrap_code="wrong",
                expected_code="existing-release-code",
                username="admin",
                display_name="Admin",
                password="ein-langes-testpasswort",
            )
        self.bootstrap()
        with self.assertRaises(PermissionError):
            self.bootstrap()

    def test_admin_can_create_viewer_and_login(self) -> None:
        admin = self.bootstrap().user
        viewer = self.store.create_user(
            username="technik.viewer",
            display_name="Technik Viewer",
            role="viewer",
            password="viewer-passwort-2026",
            actor_user_id=admin.user_id,
        )

        login = self.store.authenticate("TECHNIK.VIEWER", "viewer-passwort-2026")

        self.assertEqual(login.user.user_id, viewer.user_id)
        self.assertEqual(login.user.role, "viewer")

    def test_wrong_password_and_expired_session_are_rejected(self) -> None:
        session = self.bootstrap()
        with self.assertRaises(PermissionError):
            self.store.authenticate("admin", "das-ist-das-falsche-passwort")
        with self.assertRaises(PermissionError):
            self.store.authenticate("admin", "kurz")

        self.now += 31 * 60

        self.assertIsNone(self.store.session_user(session.token))

    def test_last_enabled_admin_cannot_be_demoted_or_disabled(self) -> None:
        admin = self.bootstrap().user

        with self.assertRaises(ValueError):
            self.store.update_user(
                user_id=admin.user_id,
                role="viewer",
                enabled=None,
                password=None,
                actor_user_id=admin.user_id,
            )
        with self.assertRaises(ValueError):
            self.store.update_user(
                user_id=admin.user_id,
                role=None,
                enabled=False,
                password=None,
                actor_user_id=admin.user_id,
            )

    def test_password_change_revokes_existing_sessions(self) -> None:
        session = self.bootstrap()

        self.store.update_user(
            user_id=session.user.user_id,
            role=None,
            enabled=None,
            password="mein-neues-langes-passwort",
            actor_user_id=session.user.user_id,
        )

        self.assertIsNone(self.store.session_user(session.token))
        self.assertEqual(
            self.store.authenticate("admin", "mein-neues-langes-passwort").user.role,
            "admin",
        )

    def test_local_admin_recovery_changes_password_and_revokes_sessions(self) -> None:
        session = self.bootstrap()

        recovered = self.store.reset_first_admin_password("temporäres-passwort-2026")

        self.assertEqual(recovered.username, "admin")
        self.assertIsNone(self.store.session_user(session.token))
        self.assertEqual(
            self.store.authenticate("admin", "temporäres-passwort-2026").user.role,
            "admin",
        )

    def test_repeated_failed_logins_are_temporarily_locked(self) -> None:
        self.bootstrap()
        for _ in range(5):
            with self.assertRaises(PermissionError):
                self.store.authenticate("admin", "das-ist-das-falsche-passwort")

        with self.assertRaisesRegex(PermissionError, "Zu viele Anmeldeversuche"):
            self.store.authenticate("admin", "ein-langes-testpasswort")

        self.now += 5 * 60 + 1

        self.assertEqual(
            self.store.authenticate("admin", "ein-langes-testpasswort").user.role,
            "admin",
        )


if __name__ == "__main__":
    unittest.main()
