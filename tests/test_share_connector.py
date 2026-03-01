import unittest
from unittest.mock import patch, MagicMock
from src.share_connector import ShareConnector

class TestShareConnector(unittest.TestCase):
    @patch('smbclient.register_session')
    @patch('smbclient.listdir')
    def test_connect_success(self, mock_listdir, mock_register):
        connector = ShareConnector(r"\\Server\Share", "user", "pass")
        mock_listdir.return_value = []
        result = connector.connect()
        self.assertTrue(result)
        mock_register.assert_called_with("Server", username="user", password="pass")
    
    @patch('smbclient.register_session')
    def test_connect_failure(self, mock_register):
        connector = ShareConnector(r"\\Server\Share", "user", "pass")
        mock_register.side_effect = Exception("Connection Failed")
        result = connector.connect()
        self.assertFalse(result)

    @patch('smbclient.scandir')
    def test_list_files(self, mock_scandir):
        connector = ShareConnector(r"\\Server\Share", "user", "pass")
        # Mock entries
        entry1 = MagicMock()
        entry1.is_file.return_value = True
        entry1.name = "file1.txt"
        entry1.stat.return_value.st_size = 100
        entry1.stat.return_value.st_mtime = 12345
        
        entry2 = MagicMock()
        entry2.is_file.return_value = False # directory
        
        mock_scandir.return_value = [entry1, entry2]
        
        files = list(connector.list_files(""))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0], ("file1.txt", 100, 12345))

if __name__ == '__main__':
    unittest.main()
