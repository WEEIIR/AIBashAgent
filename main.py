# wsl_ai_agent_module.py
# Bu modül, verilen bir görevi yerine getirmek için Gemini API'yi kullanarak
# bash komutları oluşturan yarı-otonom bir AI ajanı içerir.

import asyncio
import json
from wsl_etkilesim_guvenli_module import WSLInteractor
import time

import API_KEY  # gizlilik için

class WSLAI:
    """
    Bir ana görevi Gemini API'den gelen komutlarla WSL üzerinde adım adım
    gerçekleştiren yarı-otonom bir AI ajanı.
    """
    def __init__(self, distro='Debian'):
        self.wsl = WSLInteractor(distro=distro)
        self.chat_history = []
        self.initial_goal = ""
        # Potansiyel olarak tehlikeli komutların listesi
        self.dangerous_commands = [
            "rm -rf /",
            "fdisk",
            "mkfs",
            "dd ",
            "shutdown",
            "reboot"
        ]

    async def _send_to_gemini(self, prompt: str) -> str:
        """
        Gemini API'ye bir istek gönderir ve yanıtı döndürür.
        """
        # Gemini API ile konuşurken bir bash komutu döndürmesi için özel bir talimat veriyoruz.
        # Bu, Gemini'nin sadece tek bir satırda komut vermesini sağlar.
        system_instruction = (
            "You are a helpful AI assistant that is an expert at executing tasks in a Linux environment. "
            "Your user is trying to complete a task. You will be given the main goal, "
            "the previous console output, and a list of previously executed commands. "
            "Your job is to determine the single, next best bash command to execute to achieve the main goal. "
            "Respond ONLY with the single bash command, without any extra explanation or text. "
            "Do not use `sudo` unless explicitly necessary and justified."
            "Do not access `/mnt` directory."
        )

        self.chat_history.append({
            "role": "user",
            "parts": [{ "text": system_instruction + "\n" + prompt }]
        })

        # Gemini API'ye fetch isteği göndermek için kullanılan kod
        # API anahtarı boş bırakılmıştır, canvas ortamında otomatik olarak sağlanacaktır.
        api_key = API_KEY.API_KEY
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"
        
        # İstek gövdesi
        payload = {
            "contents": self.chat_history
        }

        # API çağrısını ve olası hataları yönetmek için bir exponential backoff döngüsü
        retries = 0
        max_retries = 5
        while retries < max_retries:
            try:
                response = await asyncio.to_thread(
                    lambda: __import__('requests').post(
                        api_url,
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps(payload),
                        timeout=10 # Zaman aşımı süresi eklendi
                    )
                )
                response.raise_for_status() # HTTP hatalarını kontrol et
                result = response.json()
                text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                return text

            except __import__('requests').exceptions.RequestException as e:
                retries += 1
                delay = 2 ** retries
                print(f"API isteği başarısız oldu, tekrar denenecek ({retries}/{max_retries}). Hata: {e}")
                time.sleep(delay)
            
            except Exception as e:
                print(f"Beklenmedik bir hata oluştu: {e}")
                return "HATA: API isteği başarısız oldu."

        return "HATA: Maksimum deneme sayısına ulaşıldı."

    def _is_command_safe(self, command: str) -> bool:
        """
        Bir komutun tehlikeli komut listesinde olup olmadığını kontrol eder.
        """
        for dangerous_cmd in self.dangerous_commands:
            if command.startswith(dangerous_cmd):
                return False
        return True

    async def run_task(self, goal: str):
        """
        AI ajanını verilen görevle başlatır ve komutları yürütür.
        """
        self.initial_goal = goal
        print(f"AI Ajanı başlatıldı. Hedef: '{self.initial_goal}'")
        
        executed_commands = []
        last_output = ""

        try:
            while True:
                # Gemini için komut istemini oluştur
                full_prompt = (
                    f"Main Goal: {self.initial_goal}\n"
                    f"Executed Commands: {'; '.join(executed_commands)}\n"
                    f"Last Console Output: {last_output}\n"
                    f"What is the single next bash command to execute?"
                )

                # Gemini'den bir sonraki komutu al
                next_command = await self._send_to_gemini(full_prompt)

                if next_command.startswith("HATA"):
                    print(f"AI Ajanı Durduruldu: {next_command}")
                    break

                # Komutun 'exit' olup olmadığını kontrol et
                if next_command.lower() == 'exit' or next_command.lower() == 'q':
                    print("\nAI Ajanı, görevin tamamlandığına karar verdi ve oturumu sonlandırıyor.")
                    break
                
                # --- GÜVENLİK KONTROLÜ ---
                if not self._is_command_safe(next_command):
                    print(f"\nTEHLİKE ALGILANDI: Yürütülmek istenen komut tehlikeli olarak işaretlendi ve engellendi: \"{next_command}\"")
                    break
                
                # Sadece komutu ve çıktıyı yazdır
                print(f"\nAPI Response: \"{next_command}\"")
                
                try:
                    # WSL'de komutu çalıştır
                    console_output = self.wsl.execute_command(next_command)
                    last_output = console_output.strip()
                    
                    if last_output:
                        print(f"Console Response: \"{last_output}\"")
                    else:
                        print("Console Response: \"\"")
                    
                    executed_commands.append(next_command)
                    
                    # Eğer görev tamamlandıysa veya bir döngü oluştuysa, durdurma mantığı eklenebilir.
                    # Basitlik için, örnekte biz manuel olarak duracağız.
                    # Örneğin, belirli bir çıktıya ulaşıldığında döngüden çıkılabilir.

                except PermissionError as e:
                    print(f"HATA: {e}")
                    last_output = str(e)
                    # Güvenlik hatası durumunda AI'nın komutu değiştirmesi için bağlamı günceller
                except Exception as e:
                    print(f"Komut yürütme hatası: {e}")
                    last_output = str(e)

        finally:
            if self.wsl.is_running():
                self.wsl.stop()

# --- BU SINIF NASIL KULLANILIR? ---
if __name__ == "__main__":
    # Windows'da asyncio döngüsünü başlatmak için
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass

    agent = WSLAI(distro='Debian')
    # Kullanıcıdan bir görev al
    task = input("AI ajanı için bir görev girin: ")
    asyncio.run(agent.run_task(task))
