<?php
// this file is to be used with XaiChatApi.py 
// for the image generation feature


$dir = __DIR__;
$files = array_filter(scandir($dir), function($f) use ($dir) {
    return $f !== '.' && $f !== '..' && is_file($dir . '/' . $f);
});
sort($files); // Alphabetical order

// Filter out index.php for display
$displayFiles = array_filter($files, function($f) {
    return $f !== 'index.php';
});

// Handle clear directory request
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['clear_dir']) && $_POST['clear_dir'] === 'yes') {
    $deleted = 0;
    foreach ($files as $file) {
        if ($file !== 'index.php') {
            if (unlink($dir . '/' . $file)) {
                $deleted++;
            }
        }
    }
    // Redirect to refresh the page
    header('Location: /generate/');
    exit;
}

$imageTypes = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'];
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grok Image Generater</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f5f5f5; color: #333; margin: 0; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border: 1px solid #ddd; }
        h1 { text-align: center; color: #333; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #f8f8f8; }
        .thumb { width: 80px; height: 60px; object-fit: cover; }
        .no-thumb { width: 80px; height: 60px; background: #eee; display: flex; align-items: center; justify-content: center; font-size: 24px; }
        .stats { text-align: center; margin-bottom: 20px; color: #666; }
        .clear-btn { display: block; margin: 20px auto; padding: 10px 20px; background: #f44336; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .clear-btn:hover { background: #d32f2f; }
        .confirm-form { text-align: center; margin: 20px 0; padding: 15px; background: #ffebee; border: 1px solid #ffcdd2; border-radius: 4px; }
        .confirm-btn { background: #4caf50; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; margin: 0 5px; }
        .confirm-btn:hover { background: #45a049; }
        a { color: #007bff; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Grook</h1>
        <div class="stats">
            <?php echo count($displayFiles); ?> images in /generate/ • Updated: <?php echo date('Y-m-d H:i:s'); ?>
        </div>
        
        <?php if (!empty($displayFiles)): ?>
            <button onclick="document.getElementById('confirm-clear').style.display='block'; this.style.display='none';" class="clear-btn">Clear Directory</button>
            <div id="confirm-clear" style="display: none;" class="confirm-form">
                <p><strong>Confirm deletion?</strong></p>
                <form method="POST" style="display: inline;">
                    <input type="hidden" name="clear_dir" value="yes">
                    <button type="submit" class="confirm-btn" style="background: #f44336;">Yes, Delete</button>
                    <button type="button" class="confirm-btn" onclick="document.getElementById('confirm-clear').style.display='none'; document.querySelector('.clear-btn').style.display='block';" style="background: #9e9e9e;">Cancel</button>
                </form>
            </div>
        <?php endif; ?>

        <?php if (empty($displayFiles)): ?>
            <p style="text-align: center; color: #666;">No files yet.</p>
        <?php else: ?>
            <table>
                <thead>
                    <tr><th>Preview</th><th>File Name</th><th>Size</th><th>Actions</th></tr>
                </thead>
                <tbody>
                    <?php foreach ($displayFiles as $file): 
                        $ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
                        $isImage = in_array($ext, $imageTypes);
                        $fileUrl = '/generate/' . urlencode($file);
                        $fileSize = filesize($dir . '/' . $file);
                        $sizeStr = $fileSize < 1024 ? $fileSize . ' B' : ($fileSize < 1048576 ? round($fileSize / 1024, 1) . ' KB' : round($fileSize / 1048576, 1) . ' MB');
                    ?>
                        <tr>
                            <td>
                                <?php if ($isImage): ?>
                                    <img src="<?php echo $fileUrl; ?>" alt="<?php echo htmlspecialchars($file); ?>" class="thumb" loading="lazy">
                                <?php else: ?>
                                    <div class="no-thumb">📄</div>
                                <?php endif; ?>
                            </td>
                            <td><?php echo htmlspecialchars($file); ?></td>
                            <td><?php echo $sizeStr; ?></td>
                            <td><a href="<?php echo $fileUrl; ?>" target="_blank">View</a></td>
                        </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        <?php endif; ?>
    </div>
</body>
</html>
