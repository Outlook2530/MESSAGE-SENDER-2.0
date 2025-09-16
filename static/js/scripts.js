function updateTokenFields() {
  var tokenType = document.getElementById('tokenType').value;
  var multiTokenFile = document.getElementById('multiTokenFile');
  var accessTokenField = document.getElementById('accessTokenField');

  if (tokenType === 'multi') {
    multiTokenFile.style.display = 'block';
    accessTokenField.style.display = 'none';
    document.getElementById('tokenFile').required = true;
    document.getElementById('accessToken').required = false;
  } else {
    multiTokenFile.style.display = 'none';
    accessTokenField.style.display = 'block';
    document.getElementById('tokenFile').required = false;
    document.getElementById('accessToken').required = true;
  }
}

// Initialize on load
window.addEventListener('load', updateTokenFields);
document.getElementById('tokenType').addEventListener('change', updateTokenFields);
