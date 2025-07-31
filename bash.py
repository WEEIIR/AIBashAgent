# wsl_etkilesim_guvenli.py
# Bu dosya, başka Python programları tarafından bir modül olarak kullanılmak üzere tasarlanmıştır.

import subprocess
import uuid

class WSLInteractor:
    """
    Çalışan bir WSL dağıtımı ile dinamik ve sürekli etkileşim kurmak için bir sınıf.
    Bu sürüm, /mnt dizinine erişimi engelleyen bir güvenlik katmanı içerir.
    """

    def __init__(self, distro='Debian'):
        """
        WSL sürecini başlatır ve iletişim kanallarını kurar.
        """
        self.distro = distro
        self.process = None
        # Benzersiz bir bitiş işaretçisi oluştur
        self.end_marker = f"END_OF_COMMAND_{uuid.uuid4()}"

        print(f"'{self.distro}' dağıtımı ile güvenli etkileşim başlatılıyor...")
        try:
            # bash'i interaktif modda (-i) başlatarak .bashrc gibi dosyaların
            # yüklenmesini ve PATH'in doğru ayarlanmasını sağlıyoruz.
            self.process = subprocess.Popen(
                ['wsl', '-d', self.distro, '-e', 'bash', '-i'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                bufsize=1
            )
            print("Bağlantı başarılı. WSL kabuğu hazır.")
            self._clear_initial_output()
        except FileNotFoundError:
            print("HATA: 'wsl.exe' bulunamadı. WSL'nin kurulu ve PATH'e ekli olduğundan emin olun.")
            raise
        except Exception as e:
            print(f"HATA: WSL süreci başlatılamadı: {e}")
            raise

    def _is_command_allowed(self, command: str) -> bool:
        """
        Komutun /mnt dizinine erişmeye çalışıp çalışmadığını kontrol eder.
        Returns:
            bool: Komuta izin veriliyorsa True, aksi takdirde False.
        """
        # Komutu boşluklara göre ayırarak her bir parçasını kontrol et
        tokens = command.split()
        for token in tokens:
            # Eğer bir parça /mnt veya /mnt/ ile başlıyorsa, bu yasak bir işlemdir.
            if token.startswith('/mnt/') or token == '/mnt':
                return False
        return True

    def _clear_initial_output(self):
        """Kabuk ilk başladığında ekrana basılan hoşgeldin mesajı gibi metinleri okuyup atlar."""
        self.execute_command("")

    def execute_command(self, command: str) -> str:
        """
        WSL kabuğuna bir komut gönderir ve çıktısını döndürür.
        /mnt dizinine erişim girişimlerini engeller.
        """
        # --- GÜVENLİK KONTROLÜ ---
        if command and not self._is_command_allowed(command):
            # Eğer komuta izin verilmiyorsa, hata fırlat ve işlemi durdur.
            raise PermissionError("Erişim Engellendi: /mnt dizini üzerindeki işlemlere izin verilmiyor.")

        if not self.is_running():
            raise ConnectionError("WSL süreci artık çalışmıyor.")

        full_command = f"{command}\necho {self.end_marker}\n"
        self.process.stdin.write(full_command)
        self.process.stdin.flush()

        output_lines = []
        while True:
            line = self.process.stdout.readline()
            # Bitiş işaretçisini ve interaktif kabuğun prompt'unu çıktıdan temizle
            if self.end_marker in line:
                break
            if line:
                output_lines.append(line)

        return "".join(output_lines)

    def is_running(self) -> bool:
        """Sürecin hala çalışıp çalışmadığını kontrol eder."""
        return self.process and self.process.poll() is None

    def stop(self):
        """WSL sürecini düzgün bir şekilde sonlandırır."""
        if self.is_running():
            print("\nWSL oturumu sonlandırılıyor...")
            self.process.stdin.write("exit\n")
            self.process.stdin.flush()
            try:
                self.process.wait(timeout=5)
                print("Oturum başarıyla kapatıldı.")
            except subprocess.TimeoutExpired:
                print("Oturum 'exit' komutuna yanıt vermedi, zorla sonlandırılıyor.")
                self.process.kill()
        self.process = None

# --- BU SINIF NASIL KULLANILIR? (Modül olarak kullanılacağı için bu bölüm yorum satırı yapılmıştır) ---
# Başka bir Python dosyasından bu modülü çağırmak için aşağıdaki gibi bir kod kullanılabilir:
# from wsl_etkilesim_guvenli import WSLInteractor
# wsl = WSLInteractor()
# wsl.execute_command("ls -l")

# if __name__ == "__main__":
#     wsl = None
#     try:
#         wsl = WSLInteractor(distro='Debian')

#         # Örnek İzin Verilen Komut:
#         print("\n--- İzin Verilen Komut: ls -l /home ---")
#         output = wsl.execute_command("ls -l /home")
#         print(f"Çıktı:\n{output.strip()}")

#         # Örnek Engellenen Komut:
#         print("\n--- Engellenen Komut: ls /mnt/c ---")
#         try:
#             wsl.execute_command("ls /mnt/c")
#         except PermissionError as e:
#             print(f"Başarıyla engellendi! Hata: {e}")
            
#         # Örnek Engellenen Komut 2 (Dosya oluşturma):
#         print("\n--- Engellenen Komut: touch /mnt/c/yeni_dosya.txt ---")
#         try:
#             wsl.execute_command("touch /mnt/c/yeni_dosya.txt")
#         except PermissionError as e:
#             print(f"Başarıyla engellendi! Hata: {e}")

#         # --- İnteraktif Mod ---
#         print("\n--- İnteraktif Moda Giriliyor (çıkmak için 'exit' yazın) ---")
#         print("NOT: /mnt dizinine erişmeye çalışırsanız hata alacaksınız.")
        
#         # Kullanıcının ev dizinini alarak prompt'ta '~' kullanabilmek için
#         home_dir = wsl.execute_command("echo $HOME").strip()

#         while True:
#             if not wsl.is_running():
#                 print("Bağlantı koptu.")
#                 break
            
#             # Prompt için dinamik bilgileri al
#             username = wsl.execute_command("whoami").strip()
#             cwd = wsl.execute_command("pwd").strip()

#             # Daha temiz bir görünüm için ev dizinini '~' ile değiştir
#             if cwd == home_dir or cwd.startswith(home_dir + '/'):
#                 display_cwd = '~' + cwd[len(home_dir):]
#             else:
#                 display_cwd = cwd

#             # Dinamik prompt'u oluştur
#             prompt = f"{username}({display_cwd})$ "

#             user_command = input(prompt)
#             if user_command.lower() == 'exit':
#                 break
            
#             try:
#                 command_output = wsl.execute_command(user_command)
#                 # Sadece bir çıktı varsa yazdır
#                 if command_output.strip():
#                     print(command_output.strip())
#             except PermissionError as e:
#                 print(f"HATA: {e}")
#             except Exception as e:
#                 print(f"Beklenmedik bir hata oluştu: {e}")

#     except Exception as e:
#         print(f"Ana programda bir hata oluştu: {e}")
#     finally:
#         if wsl and wsl.is_running():
#             wsl.stop()
