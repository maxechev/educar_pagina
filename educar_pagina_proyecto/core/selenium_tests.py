"""Pruebas de regresión de navegador para los flujos principales del sitio."""

from datetime import date
import os
import shutil
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from .models import Persona, PersonalAdministrativo, Usuario


@override_settings(
    ALLOWED_HOSTS=["localhost", "127.0.0.1", "testserver"],
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
    SECURE_HSTS_SECONDS=0,
)
class LoginBrowserRegressionTests(StaticLiveServerTestCase):
    """Comprueba desde Chrome que el inicio de sesión conserve sus validaciones."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1440,1000")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        browser_binary = (
            os.getenv("CHROME_BIN")
            or os.getenv("CHROME_PATH")
            or shutil.which("google-chrome")
            or shutil.which("chrome")
        )
        if not browser_binary and os.name == "nt":
            windows_candidates = (
                Path(os.environ.get("PROGRAMFILES", ""))
                / "Google/Chrome/Application/chrome.exe",
                Path(os.environ.get("PROGRAMFILES(X86)", ""))
                / "Google/Chrome/Application/chrome.exe",
                Path(os.environ.get("LOCALAPPDATA", ""))
                / "Google/Chrome/Application/chrome.exe",
            )
            browser_binary = next(
                (str(candidate) for candidate in windows_candidates if candidate.is_file()),
                None,
            )
        if browser_binary:
            options.binary_location = browser_binary
        cls.browser = webdriver.Chrome(options=options)
        cls.wait = WebDriverWait(cls.browser, 10)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.quit()
        super().tearDownClass()

    def setUp(self):
        self.browser.delete_all_cookies()
        usuario = Usuario.objects.create(
            nombre_usuario="selenium_admin",
            contrasenia=make_password("clave-correcta"),
            rol="administrativo",
            estado="Activo",
        )
        persona = Persona.objects.create(
            id_usuario=usuario,
            dni="99000123",
            nombre="Usuario",
            apellido="Prueba Selenium",
            fecha_nacimiento=date(1990, 1, 1),
        )
        PersonalAdministrativo.objects.create(
            id_persona=persona,
            sector="Administración",
            cargo="Administrador",
            fecha_ingreso=date.today(),
        )

    def abrir_login(self):
        self.browser.get(f"{self.live_server_url}/login/")

    def test_rechaza_una_contrasenia_incorrecta(self):
        """Regresión: credenciales inválidas no deben iniciar una sesión."""
        self.abrir_login()
        Select(self.browser.find_element(By.ID, "rol")).select_by_value(
            "administrativo"
        )
        self.browser.find_element(By.ID, "usuario").send_keys("selenium_admin")
        self.browser.find_element(By.ID, "password").send_keys("clave-incorrecta")
        self.browser.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        self.wait.until(
            EC.text_to_be_present_in_element(
                (By.TAG_NAME, "body"), "Datos incorrectos"
            )
        )
        self.assertIn("/login/", self.browser.current_url)

    def test_no_envia_el_formulario_sin_rol(self):
        """Regresión: la validación del navegador exige seleccionar un rol."""
        self.abrir_login()
        self.browser.find_element(By.ID, "usuario").send_keys("selenium_admin")
        self.browser.find_element(By.ID, "password").send_keys("clave-correcta")
        self.browser.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        alert = self.wait.until(EC.alert_is_present())
        self.assertEqual(alert.text, "Debe completar todos los campos.")
        alert.accept()
        self.assertIn("/login/", self.browser.current_url)
