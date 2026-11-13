<?php
declare(strict_types=1);
ini_set('display_errors','0');
header('Cache-Control: no-store');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
if (($_SERVER['HTTPS']??'')!=='on' && ($_SERVER['HTTPS']??'')!=='1') { http_response_code(400);exit('Требуется HTTPS'); }
session_set_cookie_params(['secure'=>true,'httponly'=>true,'samesite'=>'Strict']);session_start();
$_SESSION['csrf']??=bin2hex(random_bytes(32));$message='';
if ($_SERVER['REQUEST_METHOD']==='POST') {
    try {
        if (!is_string($_POST['csrf']??null) || !hash_equals($_SESSION['csrf'],$_POST['csrf'])) throw new RuntimeException();
        require __DIR__.'/../../lerdon-pay-private/bootstrap.php';
        $billing->rate('cancel',$_SERVER['REMOTE_ADDR']??'unknown',10,3600);
        $token=$_POST['code']??'';if (!is_string($token)) throw new RuntimeException();
        $a=$billing->authenticate(trim($token));$result=$billing->cancel($a['id']);$message=$result['message'];
        $_SESSION['csrf']=bin2hex(random_bytes(32));
    } catch (Throwable) { $message='Не удалось отключить продление. Проверьте личный код или обратитесь в поддержку.'; }
}
function esc(string $s): string {return htmlspecialchars($s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}
?>
<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lerdon — отмена подписки</title>
<style>body{background:#0b1018;color:#eee;font:18px/1.6 system-ui;padding:20px}main{max-width:580px;margin:5vh auto}input,button{box-sizing:border-box;width:100%;padding:14px;margin:10px 0;font:inherit;border-radius:8px}button{background:#d9b975;cursor:pointer}a{color:#d9b975}</style>
<main><h1>Управление подпиской</h1><p>Введите личный код восстановления из игры. Отмена отключает будущие продления и сохраняет уже оплаченный срок. Списание, которое уже было отправлено в банк, отменой продления не возвращается.</p>
<p role="status"><?=esc($message)?></p><form method="post">
<input type="hidden" name="csrf" value="<?=esc($_SESSION['csrf'])?>">
<label>Личный код<input name="code" type="password" required maxlength="64" autocomplete="off"></label>
<button type="submit">Отключить автопродление</button></form><a href="mailto:lerdonia@mail.ru">Помощь с оплатой и возвратами</a></main></html>
